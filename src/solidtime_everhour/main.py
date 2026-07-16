"""Main entry point for solidtime-everhour-sync."""

import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

from .config import Config
from .sync.structure import sync_structure
from .sync.time_entries import sync_time_entries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _parse_flag(argv: list[str], name: str) -> str | None:
    """Extract a value for `--name VALUE` from argv (consumed in order)."""
    if name not in argv:
        return None
    idx = argv.index(name)
    if idx + 1 >= len(argv):
        raise SystemExit(f"Flag {name} expects a value")
    return argv[idx + 1]


def run_sync(
    skip_structure: bool = False,
    project: str | None = None,
    client: str | None = None,
) -> None:
    """Run a sync cycle.

    Args:
        skip_structure: when True, only Phase 2 runs.
        project: if set, only Phase 2 entries under this Solidtime project.
        client: if set, only Phase 2 entries under this Solidtime client.
    """
    logger.info("=" * 60)
    logger.info("Starting sync cycle")
    logger.info("=" * 60)

    if not skip_structure:
        config = Config.load()
        logger.info("─── Phase 1: Structure Sync (Everhour → Solidtime) ───")
        try:
            sync_structure(config)
        except Exception as e:
            logger.error(f"Structure sync failed: {e}", exc_info=True)
    else:
        logger.info("─── Phase 1: SKIPPED (--skip-structure) ───")

    # Reload config to get fresh mappings
    config = Config.load()

    scope = []
    if project:
        scope.append(f"project={project}")
    if client:
        scope.append(f"client={client}")
    if not skip_structure and not scope:
        scope.append("all projects")

    logger.info(
        "─── Phase 2: Time Entry Sync (Solidtime → Everhour)"
        + (f" [{', '.join(scope)}]" if scope else "")
        + " ───"
    )
    try:
        sync_time_entries(config, project_name=project, client_name=client)
    except Exception as e:
        logger.error(f"Time entry sync failed: {e}", exc_info=True)

    logger.info("Sync cycle complete.\n")


def main() -> None:
    """Main entry point - run once or as daemon."""
    skip_structure = "--skip-structure" in sys.argv
    project = _parse_flag(sys.argv, "--project")
    client = _parse_flag(sys.argv, "--client")

    if "--once" in sys.argv:
        run_sync(skip_structure=skip_structure, project=project, client=client)
        return

    # Run as a daemon with scheduled syncs
    config = Config.load()
    interval = config.sync.schedule_minutes
    skip_structure = skip_structure or config.sync.skip_structure
    project = project or config.sync.project
    client = client or config.sync.client

    logger.info(f"Starting solidtime-everhour-sync daemon (interval: {interval}min)")
    logger.info(f"Structure sync: {'DISABLED (skip-structure)' if skip_structure else 'ENABLED'}")
    if project:
        logger.info(f"Time entry scope: project={project!r}")
    if client:
        logger.info(f"Time entry scope: client={client!r}")
    logger.info("Running initial sync...")
    run_sync(skip_structure=skip_structure, project=project, client=client)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_sync,
        "interval",
        minutes=interval,
        kwargs={"skip_structure": skip_structure, "project": project, "client": client},
    )

    logger.info(f"Scheduler started. Next sync in {interval} minutes.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")

