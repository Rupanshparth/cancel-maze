"""Generic eval runner. No business-task-specific logic belongs here."""
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable


def load_cases(path: str) -> list[dict]:
    cases = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        raise ValueError(f"duplicate test case ids: {dupes}")
    return cases


@dataclass
class CaseResult:
    id: str
    category: str
    passed: bool
    scores: list[dict] = field(default_factory=list)
    prediction: Any = None
    error: str | None = None
    latency_s: float = 0.0
    case: dict = field(default_factory=dict)


Scorer = Callable[[dict, Any], dict]
PredictFn = Callable[[dict], Any]


def run(
    cases: list[dict],
    predict_fn: PredictFn,
    scorers: list[Scorer],
    on_case: Callable[[CaseResult], None] | None = None,
) -> list[CaseResult]:
    """Run predict_fn over every case, score each with every scorer.

    A case passes only if every required scorer returns passed=True
    (scorers are required unless they return "required": False). An exception
    in predict_fn is captured as a failed case rather than raised, so one
    bad case doesn't kill the whole run.
    """
    results = []
    for case in cases:
        start = time.monotonic()
        try:
            prediction = predict_fn(case)
            error = None
        except Exception as e:  # noqa: BLE001 - eval harness must not die on one case
            prediction = None
            error = f"{type(e).__name__}: {e}"
        latency = time.monotonic() - start

        scores = []
        if error is None:
            for scorer in scorers:
                scores.append(scorer(case, prediction))
        # Scorers may return "required": False to be informational only:
        # tracked per scorer in the report but not counted against the case.
        passed = error is None and all(
            s["passed"] for s in scores if s.get("required", True)
        )

        result = CaseResult(
            id=case["id"],
            category=case.get("category", "uncategorized"),
            passed=passed,
            scores=scores,
            prediction=prediction,
            error=error,
            latency_s=latency,
            case=case,
        )
        results.append(result)
        if on_case:
            on_case(result)
    return results


def save_results_json(results: list[CaseResult], path: str) -> None:
    payload = [
        {
            "id": r.id,
            "category": r.category,
            "passed": r.passed,
            "scores": r.scores,
            "usage": (r.prediction.get("usage") if isinstance(r.prediction, dict) else None),
            "error": r.error,
            "latency_s": r.latency_s,
        }
        for r in results
    ]
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
