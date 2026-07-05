#!/usr/bin/env python3
"""Score agent-produced model-change packages against golden extraction cases."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_evals  # noqa: E402


@dataclass
class BenchmarkResult:
    passed: bool
    metrics: dict[str, dict[str, float | int]]
    errors: list[str]
    cases: list[dict[str, Any]]
    manifest: dict[str, Any] | None


def run_benchmark(
    golden_dir: Path | str,
    packages_dir: Path | str,
    *,
    min_f1: float = 0.8,
) -> BenchmarkResult:
    golden_dir = Path(golden_dir)
    packages_dir = Path(packages_dir)
    errors: list[str] = []
    case_results: list[dict[str, Any]] = []

    cases = _load_golden_cases(golden_dir, errors)
    manifest = _load_manifest(packages_dir, errors)
    manifest_cases = _manifest_case_map(manifest, errors) if manifest else {}

    totals = _new_counts()
    per_kind: dict[str, dict[str, int]] = {}

    for case in cases:
        case_id = case["case_id"]
        case_errors = list(case["errors"])
        package_path = _package_path_for_case(
            case_id,
            packages_dir,
            manifest_cases,
            case_errors,
        )
        if package_path:
            _validate_manifest_case(case, manifest_cases.get(case_id), case_errors)
        package = _load_package(package_path, case_errors) if package_path else None
        if package_path and package is not None:
            case_errors.extend(
                run_evals.check_model_change_package(package_path.parent, {"path": package_path.name})
            )

        actual_changes = package.get("changes", []) if isinstance(package, dict) else []
        if not isinstance(actual_changes, list):
            actual_changes = []
        _check_change_safety(case, actual_changes, case_errors)
        counts = _score_case(case["expected_changes"], actual_changes)
        _add_counts(totals, counts)
        _add_per_kind(per_kind, counts)

        case_result = {
            "case_id": case_id,
            "passed": not case_errors,
            "package_path": str(package_path.relative_to(packages_dir)) if package_path else None,
            "metrics": _metrics({"total": counts})["total"],
            "expected_changes": case["expected_changes"],
            "actual_changes": _summarize_changes(actual_changes),
            "errors": case_errors,
        }
        if case_errors:
            errors.extend(f"{case_id}: {error}" for error in case_errors)
        case_results.append(case_result)

    metrics = _metrics({"total": totals, **per_kind})
    if metrics["total"]["f1"] < min_f1:
        errors.append(
            "total F1 below threshold: "
            f"{metrics['total']['f1']:.3f} < {min_f1:.3f}"
        )

    result = BenchmarkResult(
        passed=not errors,
        metrics=metrics,
        errors=errors,
        cases=case_results,
        manifest=manifest,
    )
    _write_scorecard(packages_dir, golden_dir, result)
    return result


def _load_golden_cases(golden_dir: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not golden_dir.is_dir():
        errors.append(f"golden directory is not a directory: {golden_dir}")
        return []

    cases: list[dict[str, Any]] = []
    for case_dir in sorted(path for path in golden_dir.iterdir() if path.is_dir()):
        case_errors: list[str] = []
        case_errors.extend(run_evals.check_source_event(case_dir, {"path": "source-event.json"}))
        event_path = case_dir / "source-event.json"
        source_text = event_path.read_text(encoding="utf-8") if event_path.is_file() else ""
        source_event = _read_json(event_path, case_errors) if event_path.is_file() else None
        expected_path = case_dir / "expected-changes.json"
        expected_changes = _read_json(expected_path, case_errors)
        if not isinstance(expected_changes, list) or not expected_changes:
            case_errors.append(f"{expected_path}: expected-changes must be a non-empty list")
            expected_changes = []
        else:
            _validate_expected_changes(case_dir.name, expected_changes, case_errors)
        cases.append(
            {
                "case_id": case_dir.name,
                "case_dir": case_dir,
                "source_event": source_event if isinstance(source_event, dict) else {},
                "source_text": source_text,
                "source_hash": _file_hash(event_path) if event_path.is_file() else None,
                "expected_changes": expected_changes,
                "errors": case_errors,
            }
        )
    if not cases:
        errors.append(f"golden directory has no case directories: {golden_dir}")
    return cases


def _validate_expected_changes(
    case_id: str,
    expected_changes: list[Any],
    errors: list[str],
) -> None:
    for index, change in enumerate(expected_changes):
        prefix = f"{case_id}: expected-changes[{index}]"
        if not isinstance(change, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if change.get("matchKey", "kind+affectedIds") != "kind+affectedIds":
            errors.append(f"{prefix}.matchKey must be 'kind+affectedIds'")
        if not isinstance(change.get("kind"), str) or not change.get("kind"):
            errors.append(f"{prefix}.kind must be a non-empty string")
        if not isinstance(change.get("affectedIds"), list):
            errors.append(f"{prefix}.affectedIds must be a list")
        elif not all(isinstance(item, str) for item in change["affectedIds"]):
            errors.append(f"{prefix}.affectedIds entries must be strings")
        if "proposedAction" in change and not isinstance(change.get("proposedAction"), str):
            errors.append(f"{prefix}.proposedAction must be a string")
        if "optional" in change and not isinstance(change.get("optional"), bool):
            errors.append(f"{prefix}.optional must be a boolean")


def _load_manifest(
    packages_dir: Path,
    errors: list[str],
) -> dict[str, Any] | None:
    manifest_path = packages_dir / "run_manifest.json"
    if not manifest_path.is_file():
        errors.append(f"{manifest_path}: run_manifest.json is required")
        return None
    manifest = _read_json(manifest_path, errors)
    if not isinstance(manifest, dict):
        errors.append(f"{manifest_path}: manifest must be a JSON object")
        return None
    required = {"agent", "cli", "model", "prompt_hash", "started_at", "finished_at", "cases"}
    missing = sorted(required - set(manifest))
    if missing:
        errors.append(f"{manifest_path}: missing fields: {', '.join(missing)}")
    for field in ("agent", "cli", "model", "prompt_hash", "started_at", "finished_at"):
        if not isinstance(manifest.get(field), str) or not manifest.get(field):
            errors.append(f"{manifest_path}: {field} must be a non-empty string")
    prompt_hash = manifest.get("prompt_hash")
    if isinstance(prompt_hash, str) and not _looks_like_sha256(prompt_hash):
        errors.append(f"{manifest_path}: prompt_hash must be sha256:<64 hex chars>")
    if not isinstance(manifest.get("cases"), list) or not manifest.get("cases"):
        errors.append(f"{manifest_path}: cases must be a non-empty list")
    return manifest


def _manifest_case_map(
    manifest: dict[str, Any],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        return result
    for index, item in enumerate(cases):
        prefix = f"run_manifest.json: cases[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("case_id", "source_event_hash", "package_path"):
            if not isinstance(item.get(field), str) or not item.get(field):
                errors.append(f"{prefix}.{field} must be a non-empty string")
        case_id = item.get("case_id")
        if isinstance(case_id, str):
            if case_id in result:
                errors.append(f"{prefix}.case_id duplicates {case_id}")
            result[case_id] = item
    return result


def _package_path_for_case(
    case_id: str,
    packages_dir: Path,
    manifest_cases: dict[str, dict[str, Any]],
    errors: list[str],
) -> Path | None:
    if manifest_cases:
        manifest_case = manifest_cases.get(case_id)
        if not manifest_case:
            errors.append("run_manifest.json has no entry for this case")
            return None
        package_path = packages_dir / str(manifest_case.get("package_path", ""))
        try:
            package_path.resolve().relative_to(packages_dir.resolve())
        except ValueError:
            errors.append("run_manifest.json package_path escapes packages directory")
            return None
        if not package_path.is_file():
            errors.append(f"package file is missing: {package_path}")
            return None
        return package_path

    return None


def _validate_manifest_case(
    case: dict[str, Any],
    manifest_case: dict[str, Any] | None,
    errors: list[str],
) -> None:
    if not manifest_case:
        return
    expected_hash = case.get("source_hash")
    actual_hash = manifest_case.get("source_event_hash")
    if expected_hash and actual_hash != expected_hash:
        errors.append(
            "source_event_hash mismatch: "
            f"{actual_hash} != {expected_hash}"
        )


def _load_package(path: Path | None, errors: list[str]) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = _read_json(path, errors)
    if not isinstance(payload, dict):
        errors.append(f"{path}: model-change package must be a JSON object")
        return None
    return payload


def _check_change_safety(
    case: dict[str, Any],
    actual_changes: list[Any],
    errors: list[str],
) -> None:
    source_text = case.get("source_text") or ""
    source_event = case.get("source_event") or {}
    source_json = json.dumps(source_event, ensure_ascii=False, sort_keys=True)
    for index, change in enumerate(actual_changes):
        if not isinstance(change, dict):
            continue
        affected_ids = change.get("affectedIds")
        if (
            change.get("proposedAction") == "prepare-staged-proposal"
            and affected_ids == ["unknown"]
        ):
            errors.append(
                "changes[{index}] must degrade to needs-info instead of "
                "prepare-staged-proposal with affectedIds ['unknown']".format(index=index)
            )
        if change.get("proposedAction") == "needs-info" and "candidateCard" in change:
            errors.append(f"changes[{index}] needs-info must not include candidateCard")
        evidence_items = change.get("evidence")
        if not isinstance(evidence_items, list):
            continue
        for evidence_index, evidence in enumerate(evidence_items):
            if not isinstance(evidence, dict):
                continue
            excerpt = evidence.get("excerpt")
            if not isinstance(excerpt, str) or not excerpt:
                continue
            if excerpt not in source_text and excerpt not in source_json:
                errors.append(
                    f"changes[{index}].evidence[{evidence_index}] excerpt is not present "
                    "verbatim in source-event.json"
                )


def _score_case(
    expected_changes: list[Any],
    actual_changes: list[Any],
) -> dict[str, Any]:
    expected = [item for item in expected_changes if isinstance(item, dict)]
    actual = [item for item in actual_changes if isinstance(item, dict)]
    matched_actual: set[int] = set()
    counts = _new_counts()
    counts["by_kind"] = {}

    for expected_change in expected:
        if expected_change.get("optional") is True:
            continue
        expected_kind = str(expected_change.get("kind"))
        match_index = None
        for index, actual_change in enumerate(actual):
            if index in matched_actual:
                continue
            if _change_matches(expected_change, actual_change):
                match_index = index
                break
        if match_index is None:
            counts["fn"] += 1
            _kind_counts(counts, expected_kind)["fn"] += 1
        else:
            matched_actual.add(match_index)
            counts["tp"] += 1
            _kind_counts(counts, expected_kind)["tp"] += 1

    for index, actual_change in enumerate(actual):
        if index in matched_actual:
            continue
        actual_kind = str(actual_change.get("kind", "unknown"))
        counts["fp"] += 1
        _kind_counts(counts, actual_kind)["fp"] += 1
    return counts


def _change_matches(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    if actual.get("kind") != expected.get("kind"):
        return False
    if sorted(actual.get("affectedIds") or []) != sorted(expected.get("affectedIds") or []):
        return False
    expected_action = expected.get("proposedAction")
    if expected_action and actual.get("proposedAction") != expected_action:
        return False
    return True


def _new_counts() -> dict[str, int]:
    return {"tp": 0, "fp": 0, "fn": 0}


def _kind_counts(counts: dict[str, Any], kind: str) -> dict[str, int]:
    by_kind = counts.setdefault("by_kind", {})
    if kind not in by_kind:
        by_kind[kind] = _new_counts()
    return by_kind[kind]


def _add_counts(total: dict[str, int], counts: dict[str, Any]) -> None:
    total["tp"] += int(counts.get("tp", 0))
    total["fp"] += int(counts.get("fp", 0))
    total["fn"] += int(counts.get("fn", 0))


def _add_per_kind(per_kind: dict[str, dict[str, int]], counts: dict[str, Any]) -> None:
    for kind, kind_counts in counts.get("by_kind", {}).items():
        target = per_kind.setdefault(kind, _new_counts())
        _add_counts(target, kind_counts)


def _metrics(counts_by_label: dict[str, dict[str, int]]) -> dict[str, dict[str, float | int]]:
    return {label: _metric_values(counts) for label, counts in sorted(counts_by_label.items())}


def _metric_values(counts: dict[str, int]) -> dict[str, float | int]:
    tp = counts["tp"]
    fp = counts["fp"]
    fn = counts["fn"]
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def _summarize_changes(changes: list[Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for change in changes:
        if not isinstance(change, dict):
            continue
        summary.append(
            {
                "changeId": change.get("changeId"),
                "kind": change.get("kind"),
                "affectedIds": change.get("affectedIds"),
                "proposedAction": change.get("proposedAction"),
            }
        )
    return summary


def _write_scorecard(
    packages_dir: Path,
    golden_dir: Path,
    result: BenchmarkResult,
) -> None:
    packages_dir.mkdir(parents=True, exist_ok=True)
    scorecard = {
        "kind": "extraction-benchmark-scorecard",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "golden_dir": str(golden_dir),
        "packages_dir": str(packages_dir),
        "manifest": result.manifest,
        "metrics": result.metrics,
        "cases": result.cases,
        "errors": result.errors,
        "passed": result.passed,
    }
    (packages_dir / "scorecard.json").write_text(
        json.dumps(scorecard, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path}: cannot read JSON ({exc})")
        return None


def _file_hash(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def _looks_like_sha256(value: str) -> bool:
    if not value.startswith("sha256:") or len(value) != 71:
        return False
    return all(char in "0123456789abcdef" for char in value.removeprefix("sha256:"))


def _format_table(metrics: dict[str, dict[str, float | int]]) -> str:
    rows = ["kind                         TP  FP  FN  precision  recall  f1"]
    for label, values in metrics.items():
        rows.append(
            f"{label:<28} {values['tp']:>2}  {values['fp']:>2}  {values['fn']:>2}  "
            f"{values['precision']:>9.3f}  {values['recall']:>6.3f}  {values['f1']:>4.3f}"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Score model-change packages produced by an extraction agent. "
            "Package paths come from <packages>/run_manifest.json."
        )
    )
    parser.add_argument("--golden", type=Path, default=Path("evals/golden"))
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--min-f1", type=float, default=0.8)
    args = parser.parse_args(argv)

    result = run_benchmark(
        args.golden,
        args.packages,
        min_f1=args.min_f1,
    )
    print(_format_table(result.metrics))
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"- {error}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
