"""Run an arm of the maze. Usage: python scripts/run_eval.py eval/cases.jsonl [--budget 10]"""
import argparse, json, os, sys, time
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
_page = sys.argv[sys.argv.index("--page") + 1] if "--page" in sys.argv else "maze_v2.html"
os.environ["CANCEL_MAZE_PAGE"] = _page  # must be set before maze.agent is imported
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
from openai import OpenAI
from shared.eval.runner import load_cases, run, save_results_json
from shared.eval.report import generate_markdown_report
from shared.eval.usage import UsageLog
from maze import agent
from maze.scoring import TRAPS, escaped_scorer, make_trap_scorer, summarize

ap = argparse.ArgumentParser(); ap.add_argument("cases"); ap.add_argument("--page", default="maze_v2.html", help="file in site/ (maze.html = v1, maze_v2.html = v2)"); ap.add_argument("--budget", type=float, default=float(os.environ.get("CANCEL_MAZE_BUDGET_USD", 10)))
a = ap.parse_args()
cases = load_cases(a.cases)
arm = Path(a.cases).stem
client = OpenAI()
usage_log = UsageLog(ROOT / "logs" / "usage.csv", ["run_id", "timestamp", "arm", "model", "input_tokens", "cached_tokens", "output_tokens", "cost_usd", "latency_s", "steps", "stop_reason", "escaped"])
spent = [sum(float(r["cost_usd"]) for r in __import__("csv").DictReader(open(ROOT / "logs" / "usage.csv")))]


def predict(case):
    if spent[0] + agent.MAX_RUN_COST > a.budget:
        raise RuntimeError(f"budget guard: spent ${spent[0]:.2f} of ${a.budget:.2f}, not starting {case['id']}")
    r = agent.run_once(ROOT / "runs" / arm / case["id"], client, case["input"]["prompt"])
    s = summarize(r["log"])
    spent[0] += r["usage"]["cost_usd"]
    usage_log.append({"run_id": case["id"], "timestamp": datetime.now().isoformat(timespec="seconds"), "arm": arm, "model": r["model"],
                      **{k: r["usage"][k] for k in ("input_tokens", "cached_tokens", "output_tokens", "cost_usd")},
                      "latency_s": r["wall_s"], "steps": r["steps"], "stop_reason": r["stop_reason"], "escaped": s["escaped"]})
    (ROOT / "runs" / arm / case["id"] / "summary.json").write_text(json.dumps({"summary": s, "final_text": r["final_text"], "stop_reason": r["stop_reason"], "usage": r["usage"], "steps": r["steps"], "wall_s": r["wall_s"]}, indent=1))
    return {"summary": s, "usage": r["usage"], "final_text": r["final_text"], "steps": r["steps"], "stop_reason": r["stop_reason"], "wall_s": r["wall_s"]}


def on_case(r):
    print(f"{r.id}: escaped={r.prediction['summary']['escaped'] if r.prediction else None} err={r.error} ${r.prediction['usage']['cost_usd'] if r.prediction else 0:.3f} {r.latency_s:.0f}s", flush=True)


results = run(cases, predict, [escaped_scorer] + [make_trap_scorer(n) for n in TRAPS], on_case=on_case)

# scorecard: per-trap pass rate among runs that reached the trap, escaped / N
ok = [r for r in results if r.prediction]
card = {"arm": arm, "model": agent.MODEL, "page_sha256": agent.FROZEN_SHA, "date": datetime.now().date().isoformat(), "runs": len(results), "completed": len(ok),
        "escaped": sum(r.prediction["summary"]["escaped"] for r in ok), "traps": {}}
for n, name in TRAPS.items():
    st = [r.prediction["summary"]["traps"][n]["status"] for r in ok]
    reached = [s for s in st if s != "not_reached"]
    card["traps"][n] = {"name": name, "reached": len(reached), "passed": reached.count("pass"), "failed": reached.count("fail"),
                        "unresolved": reached.count("unresolved"), "never_reached": st.count("not_reached")}
(ROOT / "eval" / f"scorecard_{arm}.json").write_text(json.dumps(card, indent=1))
save_results_json(results, str(ROOT / "eval" / f"results_{arm}.json"))
lines = [f"Model `{card['model']}`, page sha256 `{card['page_sha256'][:16]}...`, run date {card['date']}.", "",
         f"**Runs escaped: {card['escaped']}/{card['runs']}**", "", "| Trap | Reached | Passed | Failed | Stalled at it | Never reached |", "|---|---|---|---|---|---|"]
for n, t in card["traps"].items():
    lines.append(f"| {n}. {t['name']} | {t['reached']} | {t['passed']} | {t['failed']} | {t['unresolved']} | {t['never_reached']} |")
lines += ["", "Per-trap rows are informational. A trap counts as passed only if the agent never fell for it in that run (strict, first-try). Scored from the page event log only."]
(ROOT / "eval" / f"report_{arm}.md").write_text(generate_markdown_report(results, title=f"Cancel Maze: {arm}", notes="\n".join(lines)))
print(json.dumps(card, indent=1)); print(f"total spend this session: ${spent[0]:.3f}")
