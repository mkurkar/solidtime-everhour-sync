"""Phase 1: Sync structure from Everhour → Solidtime.

Pulls projects and tasks from Everhour (which mirrors Linear)
and creates matching structure in Solidtime under a single Client.
"""

import logging

from ..api.everhour import EverhourClient
from ..api.solidtime import SolidtimeClient
from ..config import Config

logger = logging.getLogger(__name__)


def sync_structure(config: Config) -> None:
    """Sync projects and tasks from Everhour to Solidtime.

    Flow:
        1. Ensure Client exists in Solidtime
        2. Fetch all projects from Everhour
        3. For each project, create/find in Solidtime
        4. Fetch tasks for each project from Everhour
        5. For each task, create/find in Solidtime
        6. Update mappings
    """
    everhour = EverhourClient(config.everhour.api_token)
    solidtime = SolidtimeClient(
        config.solidtime.base_url,
        config.solidtime.api_token,
        config.solidtime.organization_id,
    )

    # Step 1: Ensure client exists
    client = solidtime.find_or_create_client(config.sync.client_name)
    client_id = client["id"]
    logger.info(f"Using client: {config.sync.client_name} ({client_id})")

    # Step 2: Fetch Everhour projects
    eh_projects = everhour.get_projects()
    logger.info(f"Found {len(eh_projects)} projects in Everhour")

    for eh_project in eh_projects:
        eh_project_id = str(eh_project["id"])
        eh_project_name = eh_project.get("name", "Unnamed Project")

        # Skip archived projects
        if eh_project.get("status") == "archived":
            logger.debug(f"Skipping archived project: {eh_project_name}")
            continue

        # Step 3: Create/find project in Solidtime
        try:
            st_project = solidtime.find_or_create_project(eh_project_name, client_id)
        except Exception as e:
            logger.warning(f"Failed to sync project '{eh_project_name}': {e}")
            continue

        st_project_id = st_project["id"]
        config.mappings.projects[eh_project_id] = st_project_id

        # Step 4: Fetch tasks for this project
        try:
            eh_tasks = everhour.get_project_tasks(eh_project_id)
        except Exception as e:
            logger.warning(f"Failed to fetch tasks for project {eh_project_name}: {e}")
            continue

        logger.info(f"  Project '{eh_project_name}': {len(eh_tasks)} tasks")

        # Step 5: Create/find tasks in Solidtime
        for eh_task in eh_tasks:
            eh_task_id = str(eh_task["id"])
            eh_task_name = eh_task.get("name", "Unnamed Task")

            # Use the Linear issue ID as part of the name if available
            # Everhour Linear tasks have IDs like "li:TEAM-123"
            task_display_name = eh_task_name
            if eh_task_id.startswith("li:"):
                linear_id = eh_task_id.replace("li:", "")
                task_display_name = f"[{linear_id}] {eh_task_name}"

            try:
                st_task = solidtime.find_or_create_task(st_project_id, task_display_name)
                config.mappings.tasks[eh_task_id] = st_task["id"]
            except Exception as e:
                logger.warning(f"    Failed to sync task '{task_display_name}': {e}")
                continue

        # Save mappings after each project to avoid losing progress on crash
        config.save_mappings()

    logger.info(
        f"Structure sync complete. "
        f"Projects: {len(config.mappings.projects)}, "
        f"Tasks: {len(config.mappings.tasks)}"
    )
