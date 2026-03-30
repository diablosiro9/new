import logging

def setup_logger():
    logger = logging.getLogger("taskmaster")
    logger.setLevel(logging.INFO)

    handler = logging.FileHandler("taskmaster.log")
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s -  %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger