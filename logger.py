import logging
from datetime import datetime


def setup_logger():
    epoch_time = int(datetime.now().timestamp())
    log_file_name = f"deployed_{epoch_time}.log"

    # Create or get the logger
    logger = logging.getLogger("app")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)  # Set the minimum log level to debug

        # Define formatter using system's local time
        formatter = logging.Formatter(
            "[%(asctime)s] [%(filename)s:%(lineno)d] (%(levelname)s) %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # File handler: logs to a file
        file_handler = logging.FileHandler(log_file_name)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        # Stream handler: logs to console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)

        # Add handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


logger = setup_logger()


def get_logger():
    return logger
