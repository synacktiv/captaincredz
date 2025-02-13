import logging
import datetime
from .cache import Cache
from importlib.util import find_spec

RICH_INSTALLED = False
if find_spec("rich"):
    RICH_INSTALLED = True
    from rich.logging import RichHandler


class Logger:
    def __init__(self, logfile, verbose=False):
        # Logging things with proper libraries
        self.logfile = logfile
        if self.logfile is None:
            self.logfile = "captaincredz.log"

        self.console_logger = logging.getLogger(__name__)
        self.file_logger = logging.getLogger("success")

        self.console_logger.setLevel(logging.DEBUG)
        self.console_stdout_handler = logging.StreamHandler()
        if RICH_INSTALLED:
            self.console_stdout_handler = RichHandler()
        if verbose:
            self.console_stdout_handler.setLevel(logging.DEBUG)
        else:
            self.console_stdout_handler.setLevel(logging.INFO)
        self.console_stdout_handler.setFormatter(
            logging.Formatter("%(levelname)s - %(message)s")
        )
        self.console_logger.addHandler(self.console_stdout_handler)

        self.file_logger.setLevel(logging.DEBUG)
        self.file_handler = logging.FileHandler(logfile)
        self.file_handler.setLevel(logging.INFO)
        self.file_handler.setFormatter(logging.Formatter("%(message)s"))
        self.file_logger.addHandler(self.file_handler)

    def error(self, message):
        self.console_logger.error(message)

    def debug(self, message):
        self.console_logger.debug(message)

    def info(self, message):
        self.console_logger.info(message)

    def log_tentative(self, username, password, ts, result, out, plugin):
        result_str = "bug"
        if result is not None:
            if type(result) == int:
                result_str = Cache.TRANSLATE_INV[result]
            elif type(result) == str:
                result_str = result
        result_left = result_str.ljust(15)
        plugin_left = plugin.ljust(15)
        date = datetime.datetime.isoformat(
            datetime.datetime.fromtimestamp(ts).replace(microsecond=0)
        )
        log_str = (
            f"{date} - {plugin_left} - {result_left} ({username}:{password}) / {out}"
        )
        self.console_logger.info(log_str)
        self.file_logger.info(log_str)
