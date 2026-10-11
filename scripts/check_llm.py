"""Why is the agent falling back to rule-based decisions? Ask Google.

    python scripts\\check_llm.py

Reads GOOGLE_API_KEY / GEMINI_MODEL from .env, lists the models your key can
actually use, tells you whether the one you configured is among them, and does
a real generateContent call to prove it works end to end.

A 'GoogleModelNotFoundError' in the decision timeline means GEMINI_MODEL names
a model your key can't reach — the agent then falls back to the deterministic
EV ranking. That fallback is by design (the graph must survive a dead model),
but for the demo you want the real thing.
"""

import os
import re
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx missing — activate the venv (.venv\\Scripts\\Activate.ps1)")

ROOT = Path(__file__).resolve().parents[1]
API = "https://generativelanguage.googleapis.com/v1beta"

GREEN, RED, YELLOW, DIM, BOLD, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m")
if os.name == "nt":
    os.system("")


def env():
    f = ROOT / ".env"
    if not f.exists():
        sys.exit(f"no .env at {f}")
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def best_model(usable):
    """Newest plain chat 'flash' model. Excludes anything that isn't a general
    text model (image/tts/audio/robotics/embedding) and anything preview/exp,
    then prefers the highest version number."""
    skip = ("preview", "exp", "image", "tts", "transcribe", "live", "omni",
            "embedding", "robotics", "computer-use", "lyria", "banana",
            "thinking", "high-res")
    cands = [m for m in usable
             if "flash" in m and "lite" not in m and not any(x in m for x in skip)]
    def version(name):
        m = re.search(r"(\d+(?:\.\d+)?)", name)
        return float(m.group(1)) if m else 0.0
    cands.sort(key=version, reverse=True)
    return cands[0] if cands else (usable[0] if usable else None)


def call(path, key, *, json_body=None):
    """Google now issues two key formats and they do NOT authenticate the same way:

      AIza...  — the classic key, sent as ?key=<key>
      AQ.Ab8...— the newer 'authentication key'; sending it as ?key= alongside
                 anything else yields "Multiple authentication credentials
                 received", so it wants the x-goog-api-key header instead.

    We try the header first (works for both), then fall back to the query
    parameter, and report which one succeeded.
    """
    attempts = [
        ("x-goog-api-key header", {"headers": {"x-goog-api-key": key}}),
        ("?key= query param", {"params": {"key": key}}),
    ]
    last = None
    for label, kwargs in attempts:
        try:
            if json_body is None:
                r = httpx.get(f"{API}/{path}", timeout=30, **kwargs)
            else:
                r = httpx.post(f"{API}/{path}", timeout=60, json=json_body, **kwargs)
        except Exception as exc:
            last = (label, None, f"{type(exc).__name__}: {exc}")
            continue
        if r.status_code == 200:
            return label, r, None
        # 404/400 is the model's problem, not the key's — no point re-trying
        # the other auth style, and doing so hides which auth actually worked.
        if r.status_code not in (401, 403):
            return label, r, r.text[:400]
        last = (label, r, r.text[:400])
    return last


def main():
    e = env()
    key = e.get("GOOGLE_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    configured = e.get("GEMINI_MODEL", "") or "gemini-2.5-flash  (the built-in default)"

    if not key:
        print(f"\n{YELLOW}GOOGLE_API_KEY is not set in .env{OFF}")
        print("The agent will use rule-based (highest-EV) decisions. That works —")
        print("but the decision timeline will say 'rule-based', not 'llm'.\n")
        print("Get a key at https://aistudio.google.com/apikey and add to .env:")
        print("    GOOGLE_API_KEY=...\n")
        return

    print(f"\n{BOLD}Configured model{OFF}  {configured}")
    print(f"{DIM}key ...{key[-6:]}{OFF}\n")

    if key.startswith("AQ."):
        print(f"{DIM}This is one of Google's newer 'AQ.' authentication keys, not a")
        print(f"classic AIza key. They authenticate differently — checking both.{OFF}\n")

    label, r, err = call("models", key)
    if r is None or r.status_code != 200:
        print(f"{RED}Google would not list models.{OFF}  (last tried: {label})")
        print(err or "")
        print(f"\n{DIM}If this says 'API key not valid', generate a fresh key at")
        print(f"https://aistudio.google.com/apikey and paste it into .env.{OFF}\n")
        return
    ok_auth = label
    print(f"  {GREEN}OK{OFF}    authenticated via {ok_auth}\n")

    models = r.json().get("models", [])
    usable = sorted(
        m["name"].removeprefix("models/") for m in models
        if "generateContent" in m.get("supportedGenerationMethods", []))

    print(f"{BOLD}Models this key can use for generateContent ({len(usable)}){OFF}")
    for name in usable:
        print(f"    {name}")

    want = e.get("GEMINI_MODEL", "gemini-2.5-flash")
    print()
    if want in usable:
        print(f"  {GREEN}OK{OFF}    '{want}' is available")
        chosen = want
    else:
        print(f"  {RED}FAIL{OFF}  '{want}' is NOT in that list — this is why the "
              f"timeline says fallback_error")
        chosen = best_model(usable)
        if not chosen:
            print(f"\n{RED}No usable model at all for this key.{OFF}")
            return
        print(f"\n  Put this in {BOLD}.env{OFF} and restart the agent:\n")
        print(f"      {BOLD}GEMINI_MODEL={chosen}{OFF}\n")

    print(f"{BOLD}Live call{OFF} — asking {chosen} to answer with one word…")
    body = {"contents": [{"parts": [{"text": "Reply with exactly one word: ready"}]}]}
    label, r, err = call(f"models/{chosen}:generateContent", key, json_body=body)

    # A model can appear in /models and still be retired for new accounts.
    # Google's 404 names the replacement — follow it rather than guessing.
    if r is not None and r.status_code == 404:
        try:
            msg = r.json()["error"]["message"]
        except Exception:
            msg = r.text
        print(f"  {RED}FAIL{OFF}  '{chosen}' is listed but not usable:")
        print(f"{DIM}    {msg[:220]}{OFF}")
        m = re.search(r"use models/([A-Za-z0-9.\-]+)", msg)
        replacement = m.group(1) if m else best_model(usable)
        if replacement and replacement != chosen:
            print(f"\n  Retrying with {BOLD}{replacement}{OFF}...")
            label, r, err = call(f"models/{replacement}:generateContent",
                                 key, json_body=body)
            if r is not None and r.status_code == 200:
                chosen = replacement
                print(f"\n  Put this in {BOLD}.env{OFF} and restart the agent:\n")
                print(f"      {BOLD}GEMINI_MODEL={chosen}{OFF}\n")

    if r is None or r.status_code != 200:
        print(f"  {RED}FAIL{OFF}  ({label}) {err}")
        return

    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        text = str(r.json())[:200]
    print(f"  {GREEN}OK{OFF}    model replied: {text!r}")
    print(f"\n{DIM}Restart the agent after changing .env, then re-run a case — the"
          f"\ndecide step should show mode 'llm' instead of 'fallback_error'.{OFF}\n")


if __name__ == "__main__":
    main()
