from src.utils.logger import setup_logger
import time

def test_logging():
    logger = setup_logger("TestLogger")
    
    logger.info("This is an INFO message. Should go to console and file.")
    logger.warning("This is a WARNING message.")
    
    print("\nSending ERROR log (should trigger Telegram)...")
    logger.error("This is an ERROR test message for Telegram Alert.")

if __name__ == "__main__":
    test_logging()
