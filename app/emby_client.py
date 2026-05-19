from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx


LOGGER = logging.getLogger("intro_marker.emby")


class EmbyClient:
    def __init__(self, base_url: str, api_key: str, user_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.user_id = user_id
        self._client = httpx.Client(timeout=30.0)

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        merged = dict(params or {})
        merged.setdefault("api_key", self.api_key)
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = self._client.request(method, url, params=merged)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            return response.json()
        return response.text

    def system_info(self) -> dict[str, Any]:
        return self._request("GET", "/System/Info")

    def list_views(self) -> dict[str, Any]:
        return self._request("GET", f"/Users/{self.user_id}/Views")

    def list_virtual_folders(self) -> list[dict[str, Any]]:
        return self._request("GET", "/Library/VirtualFolders")

    def list_episode_items(self, start_index: int = 0, limit: int = 200) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/Users/{self.user_id}/Items",
            params={
                "Recursive": "true",
                "IncludeItemTypes": "Episode",
                "Fields": "Path,ProviderIds,ParentId,SeriesName",
                "Limit": str(limit),
                "StartIndex": str(start_index),
            },
        )

    def build_path_item_index(self, roots: list[Path]) -> dict[str, str]:
        normalized_roots = [str(root).replace("\\", "/").rstrip("/") for root in roots]
        mapping: dict[str, str] = {}
        start_index = 0
        total = 1
        while start_index < total:
            payload = self.list_episode_items(start_index=start_index, limit=200)
            items = payload.get("Items", [])
            total = int(payload.get("TotalRecordCount", len(items)))
            for item in items:
                path = item.get("Path")
                item_id = item.get("Id")
                if not path or not item_id:
                    continue
                normalized_path = path.replace("\\", "/")
                if normalized_roots and not any(normalized_path.startswith(root) for root in normalized_roots):
                    continue
                mapping[normalized_path] = item_id
            start_index += len(items)
            if not items:
                break
        LOGGER.info("Built Emby episode path index with %s entries", len(mapping))
        return mapping

    def resolve_library_scan_roots(self, include_library_names: list[str]) -> list[Path]:
        include = {name.strip() for name in include_library_names if name.strip()}
        folders = self.list_virtual_folders()
        roots: list[Path] = []
        for folder in folders:
            name = folder.get("Name", "")
            if include and name not in include:
                continue
            for location in folder.get("Locations", []):
                path = Path(location)
                if path.exists():
                    roots.append(path)
                else:
                    LOGGER.warning("Skipping unavailable Emby library path: %s", path)
        return roots
