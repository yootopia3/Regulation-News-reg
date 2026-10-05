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
    pipeline = None
    try:
        pipeline = Pipeline(CONFIG_PATH)
        pipeline.run()
    except Exception as e:
        logger.critical(f"Fatal error in main loop: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Only a completed cycle can set this true. No secrets/article content
        # cross the workflow boundary, including on a partial-failure exit.
        output_path = os.environ.get('GITHUB_OUTPUT')
        if output_path:
            ready = bool(pipeline and getattr(pipeline, 'automation_ready', False))
            with open(output_path, 'a', encoding='utf-8') as output:
                output.write(f"automation_ready={'true' if ready else 'false'}\n")

if __name__ == "__main__":
    main()
