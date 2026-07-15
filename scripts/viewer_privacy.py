#!/usr/bin/env python3
"""Fail-closed privacy checks for the public model-viewer bundle."""
from __future__ import annotations

import re
from typing import Any


POLICY_ID = "public-viewer-v1"
EMAIL_RE = re.compile(r"(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9._%+-])", re.IGNORECASE)
TRANSPORT_ID_RE = re.compile(
    r"(?<![A-Z0-9])(?:telegram|tg):(?:user:)?[0-9]{4,}(?![A-Z0-9])",
    re.IGNORECASE,
)
PHONE_RE = re.compile(r"(?<![A-Z0-9])(?:tel:)?\+\d(?:[\s().-]*\d){8,14}(?![A-Z0-9])", re.IGNORECASE)
SECRET_RES = (
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
RAW_WORKING_FIELDS = {
    "excerpt",
    "locator",
    "rawPayload",
    "raw_payload",
    "rawTranscript",
    "raw_transcript",
    "transcriptBody",
    "transcript_body",
}


def contains_direct_identity(value: object) -> bool:
    text = str(value or "")
    return bool(EMAIL_RE.search(text) or TRANSPORT_ID_RE.search(text))


def _path(parts: tuple[object, ...]) -> str:
    rendered = ""
    for part in parts:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered += ("." if rendered else "") + str(part)
    return rendered or "$"


def privacy_violations(bundle: object) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []

    def add(kind: str, parts: tuple[object, ...]) -> None:
        item = {"kind": kind, "path": _path(parts)}
        if item not in violations:
            violations.append(item)

    def visit(value: object, parts: tuple[object, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_parts = (*parts, str(key))
                root = parts[0] if parts else None
                if root == "openHumanRequests" and key in {"channel", "messageRef"}:
                    add("private-routing-field", child_parts)
                if root == "reviewItems" and key == "messageRef":
                    add("private-routing-field", child_parts)
                if root in {"workingCards", "workingModel"} and key in RAW_WORKING_FIELDS:
                    add("raw-source-field", child_parts)
                visit(child, child_parts)
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, (*parts, index))
            return
        if not isinstance(value, str):
            return
        if EMAIL_RE.search(value):
            add("email-address", parts)
        if TRANSPORT_ID_RE.search(value):
            add("direct-transport-identity", parts)
        if PHONE_RE.search(value):
            add("phone-number", parts)
        if any(pattern.search(value) for pattern in SECRET_RES):
            add("secret-like-value", parts)

    visit(bundle, ())
    return sorted(violations, key=lambda item: (item["path"], item["kind"]))


def privacy_report(bundle: object) -> dict[str, Any]:
    violations = privacy_violations(bundle)
    report: dict[str, Any] = {
        "status": "failed" if violations else "passed",
        "policy": POLICY_ID,
    }
    if violations:
        report["violations"] = violations
    return report
