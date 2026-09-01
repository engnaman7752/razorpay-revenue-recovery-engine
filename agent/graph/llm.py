"""The LLM chooser used by the decide node (Phase 4).

Gemini via langchain-google-genai, temperature=0, JSON-only instruction.
One retry on a bad reply, then fall back to the top-EV action — the agent
must keep working when the model misbehaves or the API is down. The
`invoke` constructor argument lets tests stub the model with a plain function.
"""

import json
import os
import re
from pathlib import Path

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
        self.available = invoke is not None or bool(os.environ.get("GOOGLE_API_KEY"))

    def _call(self, prompt: str) -> str:
        if self._invoke is not None:
            return self._invoke(prompt)
        if self._client is None:
            from langchain_google_genai import ChatGoogleGenerativeAI
            self._client = ChatGoogleGenerativeAI(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                temperature=0)
        return self._client.invoke(prompt).content

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
                return (candidates[0],
                        f"fallback: LLM error ({type(e).__name__})", "fallback_error")
            parsed = _parse(raw)
            if parsed and parsed.get("action") in candidates:
                reason = str(parsed.get("reason", "")).strip()[:300] or "no reason given"
                return parsed["action"], reason, "llm" if attempt == 1 else "llm_retry"

        return candidates[0], "fallback: LLM parse failure", "fallback_parse"
