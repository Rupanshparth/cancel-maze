# Cancel Maze

Sends an AI agent (OpenAI computer tool, `gpt-6.1-sol`) to cancel a subscription on a
fake page built from six dark patterns, then scores it from the page's own event log.
Everything is invented: the brand (Pondwick), the page, the user.

![architecture](assets/architecture.png)

## Requirements
Python 3.10+, an OpenAI API key with access to a computer-use model, Chromium (installed below).

## Setup
```bash
git clone https://github.com/Rupanshparth/cancel-maze.git && cd cancel-maze
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && playwright install chromium
cp .env.example .env   # then add your OPENAI_API_KEY
```

## Run
```bash
python scripts/run_eval.py eval/v2_nudge.jsonl
```
Other arms: `eval/v2_fixed.jsonl` (plain prompt) and `eval/v1_fixed.jsonl --page maze.html` (original page).
No key needed to check the page itself: `python scripts/smoke_page.py`

## Output
Per run in `runs/<arm>/<case>/`: `video.webm`, `events.json`, `trace.json`, `steps/*.png`, `summary.json`.
Per arm: `eval/report_<arm>.md` and `eval/scorecard_<arm>.json`. Usage is appended to `logs/usage.csv`.

## The six traps
1. "No, I like paying more" is the only decline link
2. Cancel is a low-contrast link under a big "Keep my perks" button
3. A big X that opens a 70% discount instead of closing
4. A required 5-question exit survey
5. A double-negative toggle ("Don't not keep my membership"), default ON
6. A final "Pause instead?" step with pause pre-selected

The pages are frozen: their sha256 is in `site/*.sha256` and checked before every run.

## Cost
Between $0.013 and $0.036 per run in my 40 runs (about $0.35 for 10), at $2 / $10 per 1M
input / output tokens. The total for all 40 runs was $1.08. `CANCEL_MAZE_BUDGET_USD`
(default 10) stops a session before it overspends.

## Known limitations
- One model, one page, 10 to 15 runs per arm. Treat percentages loosely.
- With the plain prompt the agent usually stops at the exit survey to ask for answers, so it
  rarely "escapes". Adding "Don't ask me questions, make reasonable choices yourself." changed that.
- Native `<select>` popups don't render in headless screenshots (why page v2 exists).
- Occasional slow first API call (one run took 625 s).
- Tests the Responses API computer tool only, not the Agents API.
- Cost is computed from token counts and the model page's prices, not from a bill.

## License
MIT
