"""Async client for the OdoDash Home Assistant API (/api/ha/*)."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT


class OdoDashError(Exception):
    """Base error for the OdoDash API."""


class OdoDashAuthError(OdoDashError):
    """The key was rejected (HTTP 401)."""


class OdoDashConnectionError(OdoDashError):
    """OdoDash could not be reached or did not answer like OdoDash."""


class OdoDashApiClient:
    """Talks to one OdoDash server with one key."""

    def __init__(self, session: aiohttp.ClientSession, url: str, api_key: str) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._api_key = api_key

    @property
    def url(self) -> str:
        """Base URL of the OdoDash server."""
        return self._url

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.request(
                    method, f"{self._url}{path}", headers=headers, json=payload
                )
                if response.status == 401:
                    raise OdoDashAuthError("OdoDash rejected the key")
                if response.status >= 500:
                    raise OdoDashConnectionError(
                        f"OdoDash answered HTTP {response.status}"
                    )
                try:
                    data = await response.json(content_type=None)
                except ValueError as err:
                    raise OdoDashConnectionError(
                        "The server did not answer with JSON; is this the OdoDash address?"
                    ) from err
        except (TimeoutError, aiohttp.ClientError) as err:
            raise OdoDashConnectionError(f"Cannot reach OdoDash: {err}") from err

        if response.status >= 400:
            message = data.get("error") if isinstance(data, dict) else None
            raise OdoDashError(message or f"OdoDash answered HTTP {response.status}")
        if not isinstance(data, dict):
            raise OdoDashConnectionError("Unexpected answer from OdoDash")
        return data

    async def async_get_status(self) -> dict[str, Any]:
        """GET /api/ha/status: {status, user, version}."""
        return await self._request("GET", "/api/ha/status")

    async def async_get_overview(self) -> dict[str, Any]:
        """GET /api/ha/overview: every vehicle with stats and alerts."""
        return await self._request("GET", "/api/ha/overview")

    async def async_add_fuel(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /api/ha/fuel/add: log a fill-up."""
        return await self._request("POST", "/api/ha/fuel/add", payload)
