"""Phase 2: Sync time entries from Solidtime → Everhour.

Reads time entries from Solidtime and pushes them to Everhour
so they appear against the correct Linear tasks.
"""

import logging
from datetime import datetime, timedelta, timezone

from ..api.everhour import EverhourClient
from ..api.solidtime import SolidtimeClient
from ..config import Config

logger = logging.getLogger(__name__)


def _compute_duration_seconds(start: str, end: str) -> int:
    """Compute duration in seconds between two ISO timestamps."""
    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    return int((end_dt - start_dt).total_seconds())


def _extract_date(start: str) -> str:
    """Extract YYYY-MM-DD date from ISO timestamp."""
    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d")


def _reverse_task_mapping(mappings_tasks: dict[str, str]) -> dict[str, str]:
    """Create reverse mapping: solidtime_task_id -> everhour_task_id."""
    return {v: k for k, v in mappings_tasks.items()}


def _resolve_project_filter(
    solidtime: SolidtimeClient, project_name: str | None
) -> str | None:
    """Look up a Solidtime project by name and return its UUID, or None.

    Returns None if `project_name` is falsy (no filter) or the project is
    not found.
    """
    if not project_name:
        return None
    projects = solidtime.get_projects()
    for p in projects:
        if p.get("name") == project_name:
            return p["id"]
    logger.warning(f"Project {project_name!r} not found in Solidtime; ignoring filter")
    return None


def _resolve_client_filter(
    solidtime: SolidtimeClient, client_name: str | None
) -> str | None:
    """Look up a Solidtime client by name and return its UUID, or None."""
    if not client_name:
        return None
    clients = solidtime.get_clients()
    for c in clients:
        if c.get("name") == client_name:
            return c["id"]
    logger.warning(f"Client {client_name!r} not found in Solidtime; ignoring filter")
    return None


def sync_time_entries(
    config: Config,
    project_name: str | None = None,
    client_name: str | None = None,
) -> None:
    """Sync time entries from Solidtime to Everhour.

    Flow:
        1. Fetch recent time entries from Solidtime (optionally scoped by
           project or client name; both filters fall back to client-side
           filtering because Solidtime's time-entries endpoint accepts but
           ignores the project_id / client_id query params).
        2. For each entry, check if already synced (via mappings)
        3. If not synced, find the matching Everhour task ID
        4. Push time record to Everhour
        5. Store mapping

    Args:
        config: loaded Config
        project_name: if set, only sync entries in this Solidtime project
            (matched by name, e.g. "eduba").
        client_name: if set, only sync entries in this Solidtime client
            (matched by name, e.g. "Zeitlabs-Jira").
    """
    everhour = EverhourClient(config.everhour.api_token)
    solidtime = SolidtimeClient(
        config.solidtime.base_url,
        config.solidtime.api_token,
        config.solidtime.organization_id,
    )

    # Build reverse mapping: solidtime_task_id -> everhour_task_id
    reverse_tasks = _reverse_task_mapping(config.mappings.tasks)

    # Resolve filter to a project_id/client_id
    project_id = _resolve_project_filter(solidtime, project_name)
    client_id = _resolve_client_filter(solidtime, client_name)

    scope_msg = ""
    if project_id:
        scope_msg = f" scoped to project {project_name!r} ({project_id[:8]}...)"
    elif client_id:
        scope_msg = f" scoped to client {client_name!r} ({client_id[:8]}...)"

    # Step 1: Fetch recent time entries from Solidtime
    now = datetime.now(timezone.utc)
    after_date = (now - timedelta(days=config.sync.days_back)).strftime("%Y-%m-%dT00:00:00Z")
    before_date = now.strftime("%Y-%m-%dT23:59:59Z")

    # Step 1: Fetch recent time entries from Solidtime (paginated).
    # Solidtime's API caps limit at 500; pull everything in 500-row pages.
    all_entries: list[dict] = []
    offset = 0
    page_size = 500
    while True:
        page = solidtime.get_time_entries(
            after=after_date, before=before_date, limit=page_size, offset=offset
        )
        if not page:
            break
        all_entries.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    # Client-side filter (Solidtime API ignores project_id / client_id
    # query params on /time-entries, so we do it ourselves).
    if project_id or client_id:
        before_count = len(all_entries)
        if project_id:
            all_entries = [
                e for e in all_entries if e.get("project_id") == project_id
            ]
        elif client_id:
            client_project_ids = {
                p["id"]
                for p in solidtime.get_projects()
                if p.get("client_id") == client_id
            }
            all_entries = [
                e
                for e in all_entries
                if e.get("project_id") in client_project_ids
            ]
        after_count = len(all_entries)
        logger.info(
            f"After filter: {after_count}/{before_count} entries match the scope"
        )

    st_entries = all_entries
    logger.info(
        f"Found {len(st_entries)} time entries in Solidtime "
        f"(last {config.sync.days_back} days{scope_msg})"
    )

    created = 0
    skipped = 0
    errors = 0

    for entry in st_entries:
        entry_id = entry["id"]

        # Step 2: Already synced?
        if entry_id in config.mappings.time_entries:
            skipped += 1
            continue

        # Step 3: Find Everhour task ID
        st_task_id = entry.get("task_id")
        if not st_task_id:
            logger.debug(f"Entry {entry_id} has no task, skipping")
            skipped += 1
            continue

        eh_task_id = reverse_tasks.get(st_task_id)
        if not eh_task_id:
            logger.warning(
                f"Entry {entry_id}: task {st_task_id} not found in mappings. "
                "Run structure sync first or check mapping."
            )
            skipped += 1
            continue

        # Step 4: Push to Everhour
        start = entry.get("start", "")
        end = entry.get("end", "")
        if not start or not end:
            logger.debug(f"Entry {entry_id} missing start/end, skipping")
            skipped += 1
            continue

        duration_seconds = _compute_duration_seconds(start, end)
        date = _extract_date(start)
        description = entry.get("description", "")

        try:
            eh_time = everhour.add_time(
                task_id=eh_task_id,
                date=date,
                time_seconds=duration_seconds,
                comment=description,
            )
            # Store mapping
            eh_time_id = str(eh_time.get("id", ""))
            config.mappings.time_entries[entry_id] = eh_time_id
            created += 1
            logger.info(
                f"  Synced entry: {date} | {duration_seconds // 60}min | "
                f"task={eh_task_id} | '{description[:40]}'"
            )
        except Exception as e:
            logger.error(f"  Failed to sync entry {entry_id}: {e}")
            errors += 1

    # Step 5: Save mappings
    config.save_mappings()
    logger.info(
        f"Time entry sync complete. "
        f"Created: {created}, Skipped: {skipped}, Errors: {errors}"
    )
