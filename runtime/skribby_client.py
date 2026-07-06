#!/usr/bin/env python3
"""Minimal Skribby REST client for the meeting recording runtime."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
import urllib.request


DEFAULT_API_URL = "https://platform.skribby.io/api/v1/bot"


class SkribbyClientError(RuntimeError):
    """Base class for Skribby adapter failures."""


class SkribbyHTTPError(SkribbyClientError):
    def __init__(self, status: int, message: str | None = None):
        self.status = status
        super().__init__(message or f"Skribby request failed with status {status}")


class SkribbyResponseError(SkribbyClientError):
    """Raised when Skribby returns a response the runtime cannot parse."""


class SkribbyTransportError(SkribbyClientError):
    """Raised when the provider cannot be reached."""


class SkribbyClient:
    def __init__(
        self,
        *,
        api_key: str,
        api_url: str = DEFAULT_API_URL,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout

    def create_bot(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", self.api_url, payload=payload)

    def fetch_bot(self, bot_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"{self.api_url.rstrip('/')}/{quote(bot_id, safe='')}")

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            raise SkribbyHTTPError(exc.code) from exc
        except (OSError, URLError) as exc:
            raise SkribbyTransportError("Skribby request could not be completed") from exc

        if status < 200 or status >= 300:
            raise SkribbyHTTPError(status)
        try:
            result = json.loads(body)
        except Exception as exc:
            raise SkribbyResponseError("Skribby response was invalid JSON") from exc
        if not isinstance(result, dict):
            raise SkribbyResponseError("Skribby response JSON was not an object")
        return result
