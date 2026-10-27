"""Optional, pluggable LLM extraction. OFF by default.

Enable by pointing LR_LLM_CMD at any command that reads one JSON object on stdin
  {"title": "...", "text": "..."}
and prints one JSON object on stdout
  {"company": "Acme", "headcount": 120, "pct": null, "kind": "layoff", "country": "United States",
   "industry": "Technology", "speculative": false}
or {} when the headline is not about a specific layoff. This keeps the pipeline provider-agnostic
(a small script calling Claude, a local model, etc.). Only headlines the regex rules miss are sent.
"""
import json
import os
import shlex
import subprocess

from .ref import INDUSTRIES


def get_llm():
    cmd = os.environ.get("LR_LLM_CMD")
    if not cmd:
        return None

    def run(title, text=""):
        try:
            p = subprocess.run(shlex.split(cmd), input=json.dumps({"title": title, "text": text}),
                               capture_output=True, text=True, timeout=60)
            d = json.loads(p.stdout or "{}")
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            return None
        if not isinstance(d, dict) or not d.get("company"):
            return None
        hc = d.get("headcount")
        return {
            "company": str(d["company"])[:80],
            "headcount": int(hc) if isinstance(hc, (int, float)) and 0 < hc < 500_000 else None,
            "pct": float(d["pct"]) if isinstance(d.get("pct"), (int, float)) and 0 < d["pct"] <= 100 else None,
            "kind": d.get("kind") if d.get("kind") in ("layoff", "closure", "buyout") else "layoff",
            "country": d.get("country"), "industry": d.get("industry") if d.get("industry") in INDUSTRIES else None,
            "speculative": bool(d.get("speculative")), "method": "llm",
        }

    return run
