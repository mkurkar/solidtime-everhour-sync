"""Everhour API client."""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.everhour.com"


class EverhourClient:
    """Client for Everhour REST API."""

    def __init__(self, api_token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "X-Api-Key": api_token,
            "Content-Type": "application/json",
            "X-Accept-Version": "1.2",
        })

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """Make a rate-limited request to the Everhour API."""
        url = f"{BASE_URL}{endpoint}"
        resp = self.session.request(method, url, **kwargs)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 10))
            logger.warning(f"Rate limited. Retrying after {retry_after}s...")
            time.sleep(retry_after)
            resp = self.session.request(method, url, **kwargs)

        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return None

    # ─── Projects ────────────────────────────────────────────────────────────

    def get_projects(self) -> list[dict]:
        """Get all projects."""
        return self._request("GET", "/projects")

    def get_project(self, project_id: str) -> dict:
        """Get a single project."""
        return self._request("GET", f"/projects/{project_id}")

    # ─── Tasks ───────────────────────────────────────────────────────────────

    def get_project_tasks(self, project_id: str) -> list[dict]:
        """Get all tasks in a project."""
        return self._request("GET", f"/projects/{project_id}/tasks")

    def get_task(self, task_id: str) -> dict:
        """Get a single task."""
        return self._request("GET", f"/tasks/{task_id}")

    # ─── Time Records ────────────────────────────────────────────────────────

    def add_time(self, task_id: str, date: str, time_seconds: int, comment: str = "") -> dict:
        """Add time to a task.

        Args:
            task_id: Everhour task ID (e.g., "li:TEAM-123" for Linear tasks)
            date: Date in YYYY-MM-DD format
            time_seconds: Duration in seconds
            comment: Optional comment
        """
        payload: dict[str, Any] = {
            "time": time_seconds,
            "date": date,
        }
        if comment:
            payload["comment"] = comment

        return self._request("POST", f"/tasks/{task_id}/time", json=payload)

    def update_time(self, time_id: int, time_seconds: int | None = None, date: str | None = None, comment: str | None = None) -> dict:
        """Update a time record."""
        payload: dict[str, Any] = {}
        if time_seconds is not None:
            payload["time"] = time_seconds
        if date is not None:
            payload["date"] = date
        if comment is not None:
            payload["comment"] = comment

        return self._request("PUT", f"/time/{time_id}", json=payload)

    def delete_time(self, time_id: int) -> None:
        """Delete a time record."""
        self._request("DELETE", f"/time/{time_id}")

    def get_project_time(self, project_id: str, from_date: str, to_date: str) -> list[dict]:
        """Get time records for a project in a date range."""
        params = {"from": from_date, "to": to_date}
        return self._request("GET", f"/projects/{project_id}/time", params=params)

    # ─── Users ───────────────────────────────────────────────────────────────

    def get_me(self) -> dict:
        """Get current authenticated user."""
        return self._request("GET", "/users/me")
