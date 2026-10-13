"""Generic markdown report generator for shared/eval results."""
from collections import defaultdict

from .runner import CaseResult


def generate_markdown_report(
    results: list[CaseResult],
    title: str = "Eval Report",
    highlight_categories: list[str] | None = None,
    notes: str | None = None,
) -> str:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = (passed / total * 100) if total else 0.0
    avg_latency = (sum(r.latency_s for r in results) / total) if total else 0.0

    by_category: dict[str, list[CaseResult]] = defaultdict(list)
    for r in results:
        by_category[r.category].append(r)

    lines = [f"# {title}", ""]
    lines.append(f"**{passed}/{total} passed ({pass_rate:.0f}%)** — avg latency {avg_latency:.2f}s per case")
    lines.append("")

    lines.append("## By category")
    lines.append("")
    lines.append("| Category | Passed | Total | Pass rate |")
    lines.append("|---|---|---|---|")
    for cat, cat_results in sorted(by_category.items()):
        cat_passed = sum(1 for r in cat_results if r.passed)
        cat_total = len(cat_results)
        lines.append(f"| {cat} | {cat_passed} | {cat_total} | {cat_passed / cat_total * 100:.0f}% |")
    lines.append("")

    scorer_stats: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        for sc in r.scores:
            scorer_stats[sc["name"]].append(bool(sc["passed"]))
    if scorer_stats:
        lines.append("## By scorer")
        lines.append("")
        lines.append("| Scorer | Passed | Total | Pass rate |")
        lines.append("|---|---|---|---|")
        for name, vals in sorted(scorer_stats.items()):
            lines.append(f"| {name} | {sum(vals)} | {len(vals)} | {sum(vals) / len(vals) * 100:.0f}% |")
        lines.append("")

    usages = [r.prediction["usage"] for r in results
              if isinstance(r.prediction, dict) and isinstance(r.prediction.get("usage"), dict)]
    if usages:
        cost = sum(u.get("cost_usd", 0.0) for u in usages)
        tin = sum(u.get("input_tokens", 0) for u in usages)
        tout = sum(u.get("output_tokens", 0) for u in usages)
        lines.append("## Usage")
        lines.append("")
        lines.append(f"- total cost: ${cost:.4f} (${cost / len(usages):.4f} per case)")
        lines.append(f"- tokens: {tin:,} in / {tout:,} out")
        lines.append("")

    if highlight_categories:
        highlighted = [r for r in results if r.category in highlight_categories]
        if highlighted:
            lines.append("## Escalation-critical cases")
            lines.append("")
            lines.append("These are cases where a wrong automatic answer would cost the business money.")
            lines.append("")
            lines.append("| ID | Category | Passed | Detail |")
            lines.append("|---|---|---|---|")
            for r in highlighted:
                detail = "; ".join(s["detail"] for s in r.scores if not s["passed"]) or (r.error or "ok")
                status = "PASS" if r.passed else "**FAIL**"
                lines.append(f"| {r.id} | {r.category} | {status} | {detail} |")
            lines.append("")

    if failed:
        lines.append("## Failures")
        lines.append("")
        for r in results:
            if r.passed:
                continue
            lines.append(f"### {r.id} ({r.category})")
            if r.error:
                lines.append(f"- error: `{r.error}`")
            for s in r.scores:
                if not s["passed"]:
                    lines.append(f"- {s['name']}: {s['detail']}")
            lines.append("")

    if notes:
        lines.append("## Notes")
        lines.append("")
        lines.append(notes)
        lines.append("")

    return "\n".join(lines)
