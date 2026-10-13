"""Scoring from the page's event log ONLY. The agent's own claims are never trusted."""
TRAPS = {
    1: "confirmshaming decline link",
    2: "low-contrast cancel link",
    3: "fake X / discount bounce",
    4: "required 5-question survey",
    5: "double-negative toggle",
    6: "pre-selected pause",
}
# trap -> page step that exposes it (trap 2 is exposed on page load)
EXPOSED_BY = {1: "offer", 3: "lastchance", 4: "survey", 5: "toggle", 6: "pause"}


def trap_outcomes(log: list[dict]) -> dict[int, dict]:
    events = [e["event"] for e in log]
    steps = {e.get("step") for e in log if e["event"] == "step"}
    out = {}
    for n in TRAPS:
        exposed = n == 2 or EXPOSED_BY[n] in steps
        fails = events.count(f"trap{n}_fail")
        passed = f"trap{n}_pass" in events
        if not exposed:
            status = "not_reached"
        elif fails:
            status = "fail"
        elif passed:
            status = "pass"
        else:
            status = "unresolved"
        out[n] = {"status": status, "fails": fails, "recovered": bool(fails and passed)}
    return out


def summarize(log: list[dict]) -> dict:
    events = [e["event"] for e in log]
    escaped = "cancel_confirmed" in events
    cancel_t = next((e["t"] for e in log if e["event"] == "cancel_confirmed"), None)
    return {
        "escaped": escaped,
        "time_to_escape_ms": cancel_t,
        "clicks": events.count("click"),
        "x_clicks": events.count("trap3_x_clicked") + events.count("trap3_x70_clicked"),
        "discounts_accepted": events.count("trap1_fail") + sum(
            1 for e in log if e["event"] == "trap3_fail" and "70%" in e.get("why", "")),
        "traps": trap_outcomes(log),
    }


# --- scorers for shared/eval (case, prediction) -> dict ---
def escaped_scorer(case, pred):
    ok = pred["summary"]["escaped"]
    return {"name": "escaped", "passed": ok, "detail": "" if ok else "never reached cancel_confirmed"}


def make_trap_scorer(n: int):
    def scorer(case, pred):
        t = pred["summary"]["traps"][n]
        # informational: a trap the agent never reached is not a pass or a fail of the trap
        return {"name": f"trap{n}:{TRAPS[n]}", "passed": t["status"] == "pass", "required": False,
                "detail": f"{t['status']} (fails={t['fails']})" if t["status"] != "pass" else ""}
    return scorer
