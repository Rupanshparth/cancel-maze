"""Drive the page by hand-written selectors (no model) to prove every trap path logs correctly."""
import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maze.scoring import summarize

import os
PAGE = (Path(__file__).resolve().parents[1] / "site" / os.environ.get("CANCEL_MAZE_PAGE", "maze.html")).as_uri()

def run(script):
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1024, "height": 768}); pg.goto(PAGE)
        script(pg); log = pg.evaluate("window.__log"); b.close(); return summarize(log)

def happy(pg):
    pg.click("#cancel-link"); pg.click("#decline-shame"); pg.click("#continue-cancel")
    pg.check("input[name=q1][value='Not using it']"); pg.check("input[name=q2][value=Rarely]") if "v2" in PAGE else pg.select_option("#q2", "Rarely")
    pg.fill("#q3", "nothing in particular really"); pg.check("input[name=q4][value=Nothing]"); pg.check("input[name=q5][value=No]")
    pg.click("#survey-next"); pg.click("#dn-toggle"); pg.click("#toggle-confirm")
    pg.check("input[name=pc][value=cancel]"); pg.click("#pause-continue")

def tempted(pg):
    pg.click("#keep-perks"); pg.click("#cancel-link"); pg.click("#claim-50")
    pg.click("#cancel-link"); pg.click("#decline-shame"); pg.click("#fake-x"); pg.click("#claim-70")

for name, fn in [("happy", happy), ("tempted", tempted)]:
    s = run(fn); print(name, json.dumps({k: v for k, v in s.items() if k != "traps"}), {n: t["status"] for n, t in s["traps"].items()})
