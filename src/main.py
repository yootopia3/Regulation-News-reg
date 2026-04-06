import os
import sys
import logging
from src.config.settings import load_env
from src.utils.logger import setup_logger
from src.pipeline import Pipeline

# Load environment variables once at program entry
load_env()

# Setup Logging (Global)
logger = setup_logger()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'agencies.json')

def main():
    try:
        pipeline = Pipeline(CONFIG_PATH)
        pipeline.run()
    except Exception as e:
        logger.critical(f"Fatal error in main loop: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
