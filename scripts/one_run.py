"""Run a single maze attempt. Usage: python scripts/one_run.py [run_dir]"""
import json, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); load_dotenv(ROOT / ".env")
from maze.agent import run_once
from maze.scoring import summarize
r = run_once(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "runs" / "probe"))
s = summarize(r["log"])
print(json.dumps({k: v for k, v in r.items() if k != "log"}, indent=1)); print({n: t["status"] for n, t in s["traps"].items()}, "escaped:", s["escaped"])
