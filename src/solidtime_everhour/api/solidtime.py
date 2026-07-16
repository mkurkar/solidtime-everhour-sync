"""Solidtime API client."""

import logging
import time as time_module
from typing import Any

import requests
from requests.exceptions import ConnectionError, Timeout

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
REQUEST_DELAY = 0.3  # seconds between requests to avoid rate limiting


class SolidtimeClient:
    """Client for Solidtime REST API."""

    def __init__(self, base_url: str, api_token: str, organization_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.organization_id = organization_id
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _org_url(self, path: str) -> str:
        """Build URL with organization prefix."""
        return f"/organizations/{self.organization_id}{path}"

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """Make a request to the Solidtime API with retry logic."""
        url = f"{self.base_url}/api/v1{endpoint}"

        for attempt in range(MAX_RETRIES):
            try:
                time_module.sleep(REQUEST_DELAY)
                resp = self.session.request(method, url, **kwargs)

                if not resp.ok:
                    try:
                        error_body = resp.json()
                    except Exception:
                        error_body = resp.text
                    logger.error(
                        f"API error {resp.status_code} for {method} {endpoint}: {error_body}"
                    )
                    resp.raise_for_status()

                if resp.content:
                    return resp.json()
                return None

            except (ConnectionError, Timeout) as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    logger.warning(
                        f"Connection error on {method} {endpoint} (attempt {attempt + 1}): "
                        f"{e}. Retrying in {wait}s..."
                    )
                    time_module.sleep(wait)
                else:
                    raise

    # ─── Clients ─────────────────────────────────────────────────────────────

    def get_clients(self) -> list[dict]:
        """Get all clients in the organization."""
        resp = self._request("GET", self._org_url("/clients"))
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    def create_client(self, name: str) -> dict:
        """Create a new client."""
        payload = {"name": name}
        resp = self._request("POST", self._org_url("/clients"), json=payload)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    def find_or_create_client(self, name: str) -> dict:
        """Find existing client by name or create a new one."""
        clients = self.get_clients()
        for client in clients:
            if client.get("name") == name:
                logger.info(f"Found existing client: {name} ({client['id']})")
                return client

        logger.info(f"Creating new client: {name}")
        return self.create_client(name)

    # ─── Projects ────────────────────────────────────────────────────────────

    def get_projects(self) -> list[dict]:
        """Get all projects in the organization."""
        resp = self._request("GET", self._org_url("/projects"))
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    def create_project(self, name: str, client_id: str, color: str = "#3b82f6") -> dict:
        """Create a new project.

        Required fields: name, color
        Optional: client_id, is_billable, billable_rate
        """
        payload = {
            "name": name,
            "color": color,
            "client_id": client_id,
            "is_billable": True,
        }
        resp = self._request("POST", self._org_url("/projects"), json=payload)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    def find_or_create_project(self, name: str, client_id: str) -> dict:
        """Find existing project by name or create a new one."""
        projects = self.get_projects()
        for project in projects:
            if project.get("name") == name:
                logger.info(f"Found existing project: {name} ({project['id']})")
                return project

        logger.info(f"Creating new project: {name}")
        return self.create_project(name, client_id)

    # ─── Tasks ───────────────────────────────────────────────────────────────

    def get_tasks(self, project_id: str) -> list[dict]:
        """Get all tasks, optionally filtered by project."""
        params = {"project_id": project_id}
        resp = self._request("GET", self._org_url("/tasks"), params=params)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    def create_task(self, project_id: str, name: str) -> dict:
        """Create a new task."""
        payload = {
            "name": name,
            "project_id": project_id,
        }
        resp = self._request("POST", self._org_url("/tasks"), json=payload)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    def find_or_create_task(self, project_id: str, name: str) -> dict:
        """Find existing task by name or create a new one."""
        tasks = self.get_tasks(project_id)
        for task in tasks:
            if task.get("name") == name:
                logger.info(f"Found existing task: {name} ({task['id']})")
                return task

        logger.info(f"Creating new task: {name}")
        return self.create_task(project_id, name)

    # ─── Time Entries ────────────────────────────────────────────────────────

    def get_time_entries(
        self,
        after: str | None = None,
        before: str | None = None,
        active: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        client_id: str | None = None,
    ) -> list[dict]:
        """Get time entries, optionally filtered.

        Args:
            after: Only entries after this datetime (ISO 8601)
            before: Only entries before this datetime (ISO 8601)
            active: Filter by active/inactive status
            limit: Max number of entries to return (max 500)
            offset: Pagination offset
            project_id: Filter to a single Solidtime project
            task_id: Filter to a single Solidtime task
            client_id: Filter to a single Solidtime client
        """
        params: dict[str, Any] = {}
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if active is not None:
            params["active"] = str(active).lower()
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        if project_id:
            params["project_id"] = project_id
        if task_id:
            params["task_id"] = task_id
        if client_id:
            params["client_id"] = client_id

        resp = self._request("GET", self._org_url("/time-entries"), params=params)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    def create_time_entry(
        self,
        start: str,
        user_id: str,
        task_id: str | None = None,
        end: str | None = None,
        description: str = "",
    ) -> dict:
        """Create a new time entry.

        Args:
            start: Start datetime in ISO 8601 format (required)
            user_id: User ID (required)
            task_id: Task ID (optional)
            end: End datetime in ISO 8601 format (optional)
            description: Entry description (optional)
        """
        payload: dict[str, Any] = {
            "user_id": user_id,
            "start": start,
        }
        if end:
            payload["end"] = end
        if task_id:
            payload["task_id"] = task_id
        if description:
            payload["description"] = description

        resp = self._request("POST", self._org_url("/time-entries"), json=payload)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    def delete_time_entry(self, time_entry_id: str) -> None:
        """Delete a time entry."""
        self._request("DELETE", self._org_url(f"/time-entries/{time_entry_id}"))
