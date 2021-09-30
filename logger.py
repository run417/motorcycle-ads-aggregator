import logging
import os
from datetime import datetime

if not os.path.exists('logs'):
    os.makedirs('logs')

DATETIME_STR = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

app_log_filename = f"logs{os.sep}app-{DATETIME_STR}.log"
formatter = logging.Formatter("%(levelname)s:%(name)s:%(lineno)d:%(asctime)s - %(message)s")
rootlogger = logging.getLogger()
fh = logging.FileHandler(filename=app_log_filename)
ch = logging.StreamHandler()

ch.setLevel(logging.INFO)
fh.setLevel(logging.INFO)

ch.setFormatter(formatter)
fh.setFormatter(formatter)

rootlogger.addHandler(fh)
rootlogger.addHandler(ch)
def get_logger(_name: str):
    logger = logging.getLogger(_name)
    logger.setLevel(logging.INFO)
    return logger
