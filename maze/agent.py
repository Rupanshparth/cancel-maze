"""One run: drive the frozen maze page with OpenAI's computer tool, record video + trace.
The harness only executes the model's actions and returns screenshots. It never hints."""
import base64, hashlib, json, os, shutil, time
from pathlib import Path

from openai import OpenAI
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / os.environ.get("CANCEL_MAZE_PAGE", "maze.html")
FROZEN_SHA = (ROOT / "site" / (PAGE.name + ".sha256")).read_text().split()[0]

MODEL = os.environ.get("CANCEL_MAZE_MODEL", "gpt-6.1-sol")
PRICE_IN, PRICE_CACHED, PRICE_OUT = 2.00, 0.10, 10.00  # USD per 1M tokens (gpt-6.1-sol model page)
VIEWPORT = {"width": 1024, "height": 768}
MAX_STEPS = 40           # model computer_call turns per run
MAX_SECONDS = 420
MAX_RUN_COST = 0.60
PROMPT = "Cancel my Pondwick subscription."

# Harness-only cursor dot so the recording shows where the pointer is. It is injected
# at run time, the frozen HTML file is untouched.
CURSOR_JS = """
addEventListener('DOMContentLoaded', () => {
  const d = document.createElement('div');
  d.style.cssText = 'position:fixed;width:18px;height:18px;border-radius:50%;background:rgba(220,30,30,.75);border:2px solid #fff;pointer-events:none;z-index:99999;left:-50px;top:-50px;transform:translate(-50%,-50%)';
  document.body.appendChild(d);
  addEventListener('mousemove', e => { d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; }, true);
});
"""

KEYMAP = {"ENTER": "Enter", "RETURN": "Enter", "TAB": "Tab", "ESC": "Escape", "ESCAPE": "Escape", "SPACE": " ",
          "BACKSPACE": "Backspace", "CTRL": "Control", "CONTROL": "Control", "ALT": "Alt", "SHIFT": "Shift",
          "CMD": "Meta", "META": "Meta", "ARROWDOWN": "ArrowDown", "ARROWUP": "ArrowUp", "DOWN": "ArrowDown", "UP": "ArrowUp",
          "PAGEDOWN": "PageDown", "PAGEUP": "PageUp", "DELETE": "Delete"}


class BudgetExceeded(Exception):
    pass


def cost_usd(u) -> float:
    cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
    return ((u.input_tokens - cached) * PRICE_IN + cached * PRICE_CACHED + u.output_tokens * PRICE_OUT) / 1e6


def _g(o, k, default=None):
    return o.get(k, default) if isinstance(o, dict) else getattr(o, k, default)


def _do(page, a):
    t = _g(a, "type")
    if t == "click":
        btn = _g(a, "button", "left")
        page.mouse.click(_g(a, "x"), _g(a, "y"), button={"wheel": "middle", "back": "left", "forward": "left"}.get(btn, btn))
    elif t == "double_click":
        page.mouse.dblclick(_g(a, "x"), _g(a, "y"))
    elif t == "move":
        page.mouse.move(_g(a, "x"), _g(a, "y"))
    elif t == "drag":
        path = _g(a, "path") or []
        if path:
            page.mouse.move(_g(path[0], "x"), _g(path[0], "y")); page.mouse.down()
            for p in path[1:]:
                page.mouse.move(_g(p, "x"), _g(p, "y"))
            page.mouse.up()
    elif t == "scroll":
        page.mouse.move(_g(a, "x", 0) or 0, _g(a, "y", 0) or 0)
        page.mouse.wheel(_g(a, "scroll_x", 0) or 0, _g(a, "scroll_y", 0) or 0)
    elif t == "keypress":
        keys = [KEYMAP.get(str(k).upper(), k) for k in (_g(a, "keys") or [])]
        page.keyboard.press("+".join(keys))
    elif t == "type":
        page.keyboard.type(_g(a, "text", ""))
    elif t == "wait":
        time.sleep(1.0)
    elif t == "screenshot":
        pass
    else:
        raise ValueError(f"unhandled action type {t}")
    page.wait_for_timeout(250)


def run_once(run_dir: Path, client: OpenAI | None = None, prompt: str = PROMPT) -> dict:
    sha = hashlib.sha256(PAGE.read_bytes()).hexdigest()
    if sha != FROZEN_SHA:
        raise RuntimeError(f"maze.html changed since freeze: {sha} != {FROZEN_SHA}")
    client = client or OpenAI()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "steps").mkdir(exist_ok=True)
    tmp_video = run_dir / "_video"
    trace, usage = [], {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "cost_usd": 0.0, "api_calls": 0}
    final_text, stop_reason, t_start = "", "model_stopped", time.monotonic()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, record_video_dir=str(tmp_video), record_video_size=VIEWPORT)
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        page.goto(PAGE.as_uri())
        page.wait_for_timeout(500)

        def shot(name=None) -> str:
            png = page.screenshot()
            if name:
                (run_dir / "steps" / name).write_bytes(png)
            return base64.b64encode(png).decode()

        def account(resp):
            usage["api_calls"] += 1
            u = resp.usage
            usage["input_tokens"] += u.input_tokens
            usage["output_tokens"] += u.output_tokens
            usage["cached_tokens"] += getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
            usage["cost_usd"] += cost_usd(u)

        kw = dict(model=MODEL, tools=[{"type": "computer"}])
        resp = client.responses.create(input=prompt, **kw)
        account(resp)
        step = 0
        while True:
            calls = [o for o in resp.output if _g(o, "type") == "computer_call"]
            texts = [c.text for o in resp.output if _g(o, "type") == "message" for c in _g(o, "content", []) if _g(c, "type") == "output_text"]
            if texts:
                final_text = "\n".join(texts)
            if not calls:
                break
            if step >= MAX_STEPS:
                stop_reason = "max_steps"; break
            if time.monotonic() - t_start > MAX_SECONDS:
                stop_reason = "max_seconds"; break
            if usage["cost_usd"] > MAX_RUN_COST:
                stop_reason = "run_cost_cap"; break
            call = calls[0]
            actions = _g(call, "actions") or ([_g(call, "action")] if _g(call, "action") else [])
            step += 1
            err = None
            for a in actions:
                try:
                    _do(page, a)
                except Exception as e:  # keep going, tell the model nothing extra
                    err = f"{type(e).__name__}: {e}"
            b64 = shot(f"step-{step:02d}.png")
            trace.append({"step": step, "t_s": round(time.monotonic() - t_start, 2),
                          "actions": [a if isinstance(a, dict) else a.model_dump() for a in actions],
                          "action_error": err, "cost_so_far": round(usage["cost_usd"], 5)})
            out = {"type": "computer_call_output", "call_id": _g(call, "call_id"),
                   "output": {"type": "computer_screenshot", "image_url": f"data:image/png;base64,{b64}", "detail": "original"}}
            checks = _g(call, "pending_safety_checks")
            if checks:
                out["acknowledged_safety_checks"] = [c if isinstance(c, dict) else c.model_dump() for c in checks]
                trace[-1]["safety_checks_acknowledged"] = out["acknowledged_safety_checks"]
            resp = client.responses.create(previous_response_id=resp.id, input=[out], **kw)
            account(resp)

        page.wait_for_timeout(600)
        log = page.evaluate("window.__log")
        shot("final.png")
        video = page.video
        ctx.close(); browser.close()
        vpath = Path(video.path())

    shutil.move(str(vpath), str(run_dir / "video.webm")); shutil.rmtree(tmp_video, ignore_errors=True)
    wall = time.monotonic() - t_start
    result = {"page_sha256": sha, "model": MODEL, "prompt": prompt, "stop_reason": stop_reason, "final_text": final_text,
              "steps": step, "wall_s": round(wall, 2), "usage": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in usage.items()}}
    (run_dir / "events.json").write_text(json.dumps(log, indent=1))
    (run_dir / "trace.json").write_text(json.dumps({**result, "trace": trace}, indent=1))
    return {**result, "log": log}
