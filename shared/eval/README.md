# shared/eval

Generic eval harness reused across weekend builds. Nothing in this
directory should know about any specific business task — a build wires
its own `predict_fn` and `scorers` into `run()`.

## Test case format (JSONL)

One JSON object per line:

```json
{
  "id": "tc-001",
  "category": "clean_pdf",
  "description": "Human-readable note about what this case exercises",
  "input": { "...": "build-defined payload" },
  "expected": { "...": "build-defined expected output" },
  "must_flag": false
}
```

- `id` — unique string, required.
- `category` — freeform tag, build-defined. Used for report breakdowns.
- `input` / `expected` — opaque to the harness; shape is entirely up to
  the build.
- `must_flag` — optional bool. Convention (not enforced by the harness):
  `true` marks a case where a wrong automatic answer would cost the
  business money, so the system must escalate it to a human rather than
  silently act. Builds use this to pull a "costliest mistakes" section
  into their report.

## Usage

```python
from shared.eval.runner import load_cases, run
from shared.eval.report import generate_markdown_report

cases = load_cases("eval/test_cases.jsonl")

def predict_fn(case):
    return my_pipeline(case["input"])

results = run(cases, predict_fn, scorers=[my_scorer_a, my_scorer_b])
report_md = generate_markdown_report(results, title="PO Inbox Eval",
                                      highlight_categories=["risk"])
open("eval/report.md", "w").write(report_md)
```

## Scorers

A scorer is `(case: dict, prediction) -> {"name": str, "passed": bool, "detail": str}`.
`shared/eval/scorers.py` ships small generic factories (`field_equals`,
`field_in_tolerance`, `list_field_match`) that read dotted paths out of
`case["expected"]` and the prediction. Builds are free to write fully
custom scorer functions instead — the runner only requires the return
shape above.

## Informational scorers, usage, cost

- A scorer may include `"required": False` in its result. It still shows up
  in the report's "By scorer" table but doesn't decide whether the case passed.
- If a prediction is a dict with `usage: {cost_usd, input_tokens, output_tokens}`,
  the report adds a Usage section.
- `usage.UsageLog(path, fields).append(row)` writes the per-run CSV.
