"""Strict workspace-local review authority policy.

The policy contains authenticated actor and channel identifiers only. It is
runtime state, not accepted ontology content, and must stay out of model
exports and public viewers.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


POLICY_VERSION = 1
REVIEW_SCOPES = {"routine", "high-risk"}
BUSINESS_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ReviewAuthorityError(ValueError):
    """Raised when a review authority policy is malformed or ambiguous."""


def load_review_authority(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReviewAuthorityError("review authority policy does not exist") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewAuthorityError("review authority policy is not valid JSON") from exc
    return validate_review_authority(payload)


def validate_review_authority(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ReviewAuthorityError("review authority policy must be an object")
    extra = sorted(set(payload) - {"policyVersion", "businessId", "channels"})
    if extra:
        raise ReviewAuthorityError("review authority policy has unexpected fields")
    if payload.get("policyVersion") != POLICY_VERSION:
        raise ReviewAuthorityError("unsupported review authority policy version")
    business_id = _required_string(payload, "businessId")
    if BUSINESS_ID_RE.fullmatch(business_id) is None:
        raise ReviewAuthorityError("review authority businessId is invalid")
    channels = payload.get("channels")
    if not isinstance(channels, list):
        raise ReviewAuthorityError("review authority channels must be an array")

    normalized_channels: list[dict[str, object]] = []
    claimed_channel_ids: set[str] = set()
    for index, raw_rule in enumerate(channels, start=1):
        if not isinstance(raw_rule, dict):
            raise ReviewAuthorityError(f"review authority channel {index} must be an object")
        extra = sorted(set(raw_rule) - {"channel", "aliases", "reviewScopes", "actors"})
        if extra:
            raise ReviewAuthorityError(
                f"review authority channel {index} has unexpected fields"
            )
        channel = _required_string(raw_rule, "channel")
        aliases = _unique_strings(raw_rule.get("aliases"), f"channel {index} aliases")
        scopes = _unique_strings(
            raw_rule.get("reviewScopes"), f"channel {index} reviewScopes"
        )
        if not scopes or not set(scopes) <= REVIEW_SCOPES:
            raise ReviewAuthorityError(
                f"review authority channel {index} has invalid reviewScopes"
            )
        actors = _unique_strings(raw_rule.get("actors"), f"channel {index} actors")
        if not actors:
            raise ReviewAuthorityError(
                f"review authority channel {index} must name at least one actor"
            )
        identifiers = [channel, *aliases]
        if len(identifiers) != len(set(identifiers)):
            raise ReviewAuthorityError(
                f"review authority channel {index} repeats its canonical channel"
            )
        overlap = claimed_channel_ids.intersection(identifiers)
        if overlap:
            raise ReviewAuthorityError("review authority channel aliases are ambiguous")
        claimed_channel_ids.update(identifiers)
        normalized_channels.append(
            {
                "channel": channel,
                "aliases": aliases,
                "reviewScopes": scopes,
                "actors": actors,
            }
        )

    return {
        "policyVersion": POLICY_VERSION,
        "businessId": business_id,
        "channels": normalized_channels,
    }


def channel_rule(
    policy: dict[str, object] | None,
    channel: str,
) -> dict[str, object] | None:
    if policy is None:
        return None
    normalized = validate_review_authority(policy)
    channels = normalized["channels"]
    assert isinstance(channels, list)
    for rule in channels:
        assert isinstance(rule, dict)
        aliases = rule["aliases"]
        assert isinstance(aliases, list)
        identifiers = {str(rule["channel"]), *(str(item) for item in aliases)}
        if channel in identifiers:
            return rule
    return None


def channels_equivalent(
    policy: dict[str, object] | None,
    left: str,
    right: str,
) -> bool:
    if left == right:
        return True
    left_rule = channel_rule(policy, left)
    right_rule = channel_rule(policy, right)
    return bool(left_rule is not None and left_rule == right_rule)


def is_review_authorized(
    policy: dict[str, object] | None,
    *,
    actor: str,
    channel: str,
    scope: str,
) -> bool:
    if scope not in REVIEW_SCOPES:
        raise ReviewAuthorityError(f"unsupported review authority scope {scope!r}")
    rule = channel_rule(policy, channel)
    if rule is None:
        return False
    actors = rule["actors"]
    scopes = rule["reviewScopes"]
    assert isinstance(actors, list)
    assert isinstance(scopes, list)
    return actor in actors and scope in scopes


def is_review_actor(
    policy: dict[str, object] | None,
    *,
    actor: str,
    channel: str,
) -> bool:
    rule = channel_rule(policy, channel)
    if rule is None:
        return False
    actors = rule["actors"]
    assert isinstance(actors, list)
    return actor in actors


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ReviewAuthorityError(f"review authority {field} must be a non-empty string")
    return value.strip()


def _unique_strings(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ReviewAuthorityError(f"review authority {label} must be an array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ReviewAuthorityError(
                f"review authority {label} must contain non-empty strings"
            )
        normalized = item.strip()
        if normalized in result:
            raise ReviewAuthorityError(f"review authority {label} must be unique")
        result.append(normalized)
    return result
