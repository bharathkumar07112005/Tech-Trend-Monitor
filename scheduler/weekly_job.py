"""
scheduler/weekly_job.py
───────────────────────
Uses the `schedule` library to run the full Tech Trend Monitor pipeline
once a week on the configured day + time.

Run this module directly to start the scheduler process:
    python -m scheduler.weekly_job

The pipeline can also be triggered manually:
    python -m scheduler.weekly_job --run-now
"""

import sys
import time
import argparse
import datetime
import pathlib

import schedule
from loguru import logger

# ── Logging setup ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from config import LOG_DIR, SCHEDULE_DAY, SCHEDULE_TIME

log_file = LOG_DIR / "scheduler.log"
logger.add(str(log_file), rotation="1 week", retention="4 weeks",
           format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


# ── Import pipeline ───────────────────────────────────────────────────────────
def _run_pipeline() -> None:
    """
    Execute the full data pipeline.  Imported lazily so this module can be
    imported without triggering heavy imports at startup.
    """
    from main import run_pipeline  # main.py in project root
    logger.info("═" * 60)
    logger.info(f"Scheduled pipeline starting at {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    try:
        run_pipeline()
        logger.success("Scheduled pipeline completed successfully.")
    except Exception as exc:
        logger.exception(f"Pipeline failed: {exc}")
    logger.info("═" * 60)


# ── Scheduler setup ───────────────────────────────────────────────────────────
def setup_schedule() -> None:
    """Register the weekly job with the schedule library."""
    day_method = getattr(schedule.every(), SCHEDULE_DAY.lower(), None)
    if day_method is None:
        raise ValueError(
            f"Invalid SCHEDULE_DAY '{SCHEDULE_DAY}'. "
            "Must be one of: monday tuesday wednesday thursday friday saturday sunday"
        )
    day_method.at(SCHEDULE_TIME).do(_run_pipeline)
    logger.info(f"Scheduled: pipeline will run every {SCHEDULE_DAY.capitalize()} at {SCHEDULE_TIME}")


def run_scheduler() -> None:
    """Block forever, running pending jobs and sleeping between checks."""
    setup_schedule()
    logger.info("Scheduler started.  Waiting for next run …")
    logger.info(f"Next run: {schedule.next_run()}")

    while True:
        schedule.run_pending()
        time.sleep(30)   # check every 30 seconds


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tech Trend Monitor – Scheduler")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute the pipeline immediately (without waiting for the scheduled time)",
    )
    args = parser.parse_args()

    if args.run_now:
        logger.info("--run-now flag detected; executing pipeline immediately.")
        _run_pipeline()
    else:
        run_scheduler()
