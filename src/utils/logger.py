import logging
import os
from logging.handlers import RotatingFileHandler
from src.services.notifier import TelegramNotifier
from src.config import settings

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
    Install project logging handlers.

    History: the original version configured only the ``"MarketPulse"``
    named logger, but every module inside ``src/`` uses
    ``logging.getLogger(__name__)`` (e.g. ``src.pipeline``,
    ``src.services.analyzer.hybrid``). Those module loggers are descendants
    of the root logger, **not** of ``"MarketPulse"``, so their ``INFO`` /
    ``WARNING`` output was silently dropped.

    Fix: install the handlers on the ``"src"`` package logger, which is the
    common ancestor of every ``src.*`` module logger. They inherit via
    normal propagation. The same handlers are also attached to the legacy
    ``name`` logger so ``setup_logger()`` callers (e.g. ``src/main.py``)
    keep a usable reference for ``logger.critical(...)``.

    Handlers:
      - RotatingFileHandler (logs/app.log)
      - StreamHandler (Console)
      - TelegramLoggingHandler (ERROR+)
    """
    package_logger = logging.getLogger("src")
    legacy_logger = logging.getLogger(name)

    # Idempotent: if already configured, just return the named logger.
    if package_logger.handlers:
        return legacy_logger

    for target in (package_logger, legacy_logger):
        target.setLevel(logging.INFO)
        # Don't double-emit through root — these two loggers are siblings
        # under root, not parent/child, so disabling propagation on both is
        # safe and avoids leaking through root's lastResort handler.
        target.propagate = False

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

    # 2. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # 3. Telegram Handler — intentionally attached ONLY to the legacy
    # logger. The legacy ("MarketPulse") logger is reserved for fatal
    # errors raised via ``setup_logger().critical(...)`` from ``src/main.py``.
    # Attaching this handler to the ``src`` package logger would cause
    # every transient module-level ERROR (e.g. an external site connection
    # reset, a single failed Gemini parse) to become a Telegram "System
    # Alert", which was never the intent. File and console handlers are
    # attached to both loggers.
    telegram_handler = TelegramLoggingHandler()
    telegram_handler.setFormatter(formatter)
    telegram_handler.setLevel(logging.ERROR)

    for target in (package_logger, legacy_logger):
        target.addHandler(file_handler)
        target.addHandler(console_handler)
    legacy_logger.addHandler(telegram_handler)

    return legacy_logger
