"""Small generic scorer factories. Operate on dotted paths so they stay
task-agnostic — a build can also just write a plain scorer function."""
from typing import Any


def _get(obj: Any, path: str) -> Any:
    """Walk a dotted path (with optional [index]) through dicts/lists."""
    cur = obj
    for part in path.split("."):
        if "[" in part and part.endswith("]"):
            key, idx = part[:-1].split("[")
            cur = cur[key] if key else cur
            cur = cur[int(idx)]
        else:
            cur = cur[part]
    return cur


def field_equals(expected_path: str, actual_path: str | None = None, name: str | None = None):
    """expected value lives at case["expected"].<expected_path>,
    actual value lives at prediction.<actual_path> (defaults to same path)."""
    actual_path = actual_path or expected_path
    scorer_name = name or f"field_equals:{expected_path}"

    def scorer(case: dict, prediction: Any) -> dict:
        try:
            expected_val = _get(case["expected"], expected_path)
            actual_val = _get(prediction, actual_path)
        except (KeyError, IndexError, TypeError) as e:
            return {"name": scorer_name, "passed": False, "detail": f"path missing: {e}"}
        passed = expected_val == actual_val
        detail = "" if passed else f"expected {expected_val!r}, got {actual_val!r}"
        return {"name": scorer_name, "passed": passed, "detail": detail}

    return scorer


def field_in_tolerance(expected_path: str, actual_path: str | None = None, tolerance: float = 0.01, name: str | None = None):
    """Numeric comparison within absolute tolerance."""
    actual_path = actual_path or expected_path
    scorer_name = name or f"field_in_tolerance:{expected_path}"

    def scorer(case: dict, prediction: Any) -> dict:
        try:
            expected_val = float(_get(case["expected"], expected_path))
            actual_val = float(_get(prediction, actual_path))
        except (KeyError, IndexError, TypeError, ValueError) as e:
            return {"name": scorer_name, "passed": False, "detail": f"path missing or not numeric: {e}"}
        passed = abs(expected_val - actual_val) <= tolerance
        detail = "" if passed else f"expected {expected_val!r}, got {actual_val!r} (tol {tolerance})"
        return {"name": scorer_name, "passed": passed, "detail": detail}

    return scorer


def list_field_match(expected_path: str, actual_path: str | None = None, key: str = "id", name: str | None = None):
    """Compares two lists of dicts by a key field, order-independent."""
    actual_path = actual_path or expected_path
    scorer_name = name or f"list_field_match:{expected_path}"

    def scorer(case: dict, prediction: Any) -> dict:
        try:
            expected_list = _get(case["expected"], expected_path)
            actual_list = _get(prediction, actual_path)
        except (KeyError, IndexError, TypeError) as e:
            return {"name": scorer_name, "passed": False, "detail": f"path missing: {e}"}
        expected_keys = {item[key] for item in expected_list}
        actual_keys = {item[key] for item in actual_list}
        passed = expected_keys == actual_keys
        detail = "" if passed else f"missing {expected_keys - actual_keys}, extra {actual_keys - expected_keys}"
        return {"name": scorer_name, "passed": passed, "detail": detail}

    return scorer
