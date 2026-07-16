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


def run_sync(skip_structure: bool = False) -> None:
    """Run a sync cycle.

    Args:
        skip_structure: when True, only Phase 2 runs (time entries only).
            Use this once your Solidtime projects/tasks match the structure
            sync and you no longer want to re-query Everhour projects.
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

    # Phase 2: Sync time entries (Solidtime → Everhour)
    logger.info("─── Phase 2: Time Entry Sync (Solidtime → Everhour) ───")
    try:
        sync_time_entries(config)
    except Exception as e:
        logger.error(f"Time entry sync failed: {e}", exc_info=True)

    logger.info("Sync cycle complete.\n")


def main() -> None:
    """Main entry point - run once or as daemon."""
    skip_structure = "--skip-structure" in sys.argv

    if "--once" in sys.argv:
        run_sync(skip_structure=skip_structure)
        return

    # Run as a daemon with scheduled syncs
    config = Config.load()
    interval = config.sync.schedule_minutes
    skip_structure = skip_structure or config.sync.skip_structure

    logger.info(f"Starting solidtime-everhour-sync daemon (interval: {interval}min)")
    logger.info(f"Structure sync: {'DISABLED (skip-structure)' if skip_structure else 'ENABLED'}")
    logger.info("Running initial sync...")
    run_sync(skip_structure=skip_structure)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_sync,
        "interval",
        minutes=interval,
        kwargs={"skip_structure": skip_structure},
    )

    logger.info(f"Scheduler started. Next sync in {interval} minutes.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
