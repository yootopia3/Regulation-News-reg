from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import os
import logging
from src.pipeline import Pipeline
from config import settings
from src.utils.logger import setup_logger

# Setup logging
logger = setup_logger("Scheduler")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'agencies.json')

def job_function():
    logger.info("Executing scheduled job...")
    try:
        pipeline = Pipeline(CONFIG_PATH)
        pipeline.run()
    except Exception as e:
        logger.critical(f"Job execution failed: {e}", exc_info=True)

def main():
    scheduler = BlockingScheduler()
    
    # Schedule key: Runs every X minutes (from settings)
    interval = settings.COLLECTION_INTERVAL_MINUTES
    scheduler.add_job(job_function, 'interval', minutes=interval, next_run_time=datetime.now())
    
    logger.info(f"Scheduler started with {interval}min interval. Press Ctrl+C to exit.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")

if __name__ == "__main__":
    main()
