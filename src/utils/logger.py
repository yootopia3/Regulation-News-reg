import logging
import os
from logging.handlers import RotatingFileHandler
from src.services.notifier import TelegramNotifier
from config import settings

class TelegramLoggingHandler(logging.Handler):
    """
    Custom logging handler that sends CRITICAL/ERROR logs via Telegram.
    """
    def __init__(self, level=logging.ERROR):
        super().__init__(level)
        try:
            self.notifier = TelegramNotifier()
        except Exception:
            self.notifier = None

    def emit(self, record):
        if not self.notifier or not self.notifier.enabled:
            return
            
        try:
            log_entry = self.format(record)
            # Add simple rate limiting or duplicate check if needed later
            msg = f"🚨 *System Alert* 🚨\n\n`{log_entry}`"
            self.notifier.send_message(msg)
        except Exception:
            self.handleError(record)

def setup_logger(name="MarketPulse"):
    """
    Sets up a logger with:
      - RotatingFileHandler (logs/app.log)
      - StreamHandler (Console)
      - TelegramLoggingHandler (ERROR+)
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Prevent double logging if attached to root

    if logger.handlers:
        return logger

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 1. File Handler
    log_path = settings.LOG_FILE_PATH
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=settings.LOG_MAX_BYTES, 
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    # 2. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 3. Telegram Handler
    telegram_handler = TelegramLoggingHandler()
    telegram_handler.setFormatter(formatter)
    telegram_handler.setLevel(logging.ERROR)
    logger.addHandler(telegram_handler)

    return logger
