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


def run_sync() -> None:
    """Run full sync cycle."""
    logger.info("=" * 60)
    logger.info("Starting sync cycle")
    logger.info("=" * 60)

    config = Config.load()

    # Phase 1: Sync structure (Everhour → Solidtime)
    logger.info("─── Phase 1: Structure Sync (Everhour → Solidtime) ───")
    try:
        sync_structure(config)
    except Exception as e:
        logger.error(f"Structure sync failed: {e}", exc_info=True)

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
    if "--once" in sys.argv:
        # Run a single sync and exit
        run_sync()
        return

    # Run as a daemon with scheduled syncs
    config = Config.load()
    interval = config.sync.schedule_minutes

    logger.info(f"Starting solidtime-everhour-sync daemon (interval: {interval}min)")
    logger.info("Running initial sync...")
    run_sync()

    scheduler = BlockingScheduler()
    scheduler.add_job(run_sync, "interval", minutes=interval)

    logger.info(f"Scheduler started. Next sync in {interval} minutes.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
