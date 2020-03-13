import logging
import logging.handlers
from pathlib import Path
from os import makedirs as make_directories

__version__ = '2020.0.1'
__app_name__ = 'zencelium'

_root_logger = logging.getLogger(__name__)
_root_logger_configured = False

BYTE = 1
KB = 1024 * BYTE
MB = 1024 * KB
GB = 1024 * MB


def configure_logging(file_path,
                      log_level=logging.WARNING,
                      file_size= 10 * MB,
                      keep_logs=10):
    global _root_logger_configured
    assert _root_logger_configured is False, 'root_logger is already configured!'

    file_formatter = logging.Formatter(
        '%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
    console_formatter = logging.Formatter(
        '%(name)-15s %(levelname)-8s %(message)s')

    log_file_path = Path(file_path)
    make_directories(log_file_path.parent, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(log_file_path, 'a', file_size, keep_logs)
    fh.setFormatter(file_formatter)
    fh.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setFormatter(console_formatter)
    ch.setLevel(log_level)

    _root_logger.addHandler(fh)
    _root_logger.addHandler(ch)
    _root_logger.setLevel(logging.DEBUG)

    _root_logger_configured = True
