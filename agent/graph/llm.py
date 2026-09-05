"""The LLM chooser used by the decide node (Phase 4).

Gemini over the REST API, temperature=0, JSON-only instruction. One retry on a
bad reply, then fall back to the top-EV action — the agent must keep working
when the model misbehaves or the API is down. The `invoke` constructor argument
lets tests stub the model with a plain function.

Why raw REST instead of langchain-google-genai: Google now issues keys in two
formats. Classic `AIza...` keys go in `?key=`; the newer `AQ.Ab8...`
authentication keys want the `x-goog-api-key` header, and sending both yields
"Multiple authentication credentials received". Client libraries lag that
change and surface it as a confusing NotFound. One httpx call that sets the
header explicitly works for both and removes a dependency from the hot path.
"""

import json
import os
import re
from pathlib import Path

import httpx

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.6-flash"

PROMPT_PATH = Path(__file__).parents[1] / "prompts" / "decide.txt"


def _parse(raw: str) -> dict | None:
    """Extract a JSON object from a model reply (tolerates code fences/prose)."""
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class DecideLLM:
    def __init__(self, invoke=None):
        self._invoke = invoke
        self._client = None
        # LLM_ENABLED=false forces the deterministic top-EV chooser even when a
        # key is present. That's the ablation switch: run the same 300 cases
        # with and without the model and the difference is attributable.
        enabled = os.environ.get("LLM_ENABLED", "true").strip().lower() \
            not in ("false", "0", "off", "no")
        self.available = invoke is not None or (
            enabled and bool(os.environ.get("GOOGLE_API_KEY")))

    def _call(self, prompt: str) -> str:
        if self._invoke is not None:
            return self._invoke(prompt)
        model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        key = os.environ["GOOGLE_API_KEY"]
        r = httpx.post(
            f"{API_BASE}/models/{model}:generateContent",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0}},
            timeout=30,
        )
        if r.status_code != 200:
            # surfaced to choose() as fallback_error, with the reason intact
            raise RuntimeError(f"gemini {r.status_code}: {r.text[:200]}")
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)

    def choose(self, context: dict, candidates: list[str]) -> tuple[str, str, str]:
        """Pick one candidate action. Returns (action, reason, mode) where mode is
        llm | llm_retry | fallback_parse | fallback_error | rule."""
        if not self.available:
            return candidates[0], "rule-based: highest EV (no GOOGLE_API_KEY)", "rule"

        prompt = PROMPT_PATH.read_text().format(
            context=json.dumps(context, indent=2),
            candidates=", ".join(candidates))

        for attempt in (1, 2):
            try:
                raw = self._call(prompt if attempt == 1 else
                                 prompt + "\n\nYour previous reply was invalid. "
                                          "Reply with ONLY the JSON object.")
            except Exception as e:
                # keep the real reason in the audit trail — a bare exception
                # class name ("GoogleModelNotFoundError") sent us chasing the
                # wrong bug once already.
                detail = str(e).strip().replace("\n", " ")[:180] or type(e).__name__
                return (candidates[0], f"fallback: LLM error ({detail})",
                        "fallback_error")
            parsed = _parse(raw)
            if parsed and parsed.get("action") in candidates:
                reason = str(parsed.get("reason", "")).strip()[:300] or "no reason given"
                return parsed["action"], reason, "llm" if attempt == 1 else "llm_retry"

        return candidates[0], "fallback: LLM parse failure", "fallback_parse"
