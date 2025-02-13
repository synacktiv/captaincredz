import importlib
from queue import SimpleQueue
from .cache import Cache
import traceback
import datetime
import sys


class Worker:
    SLEEP_INTERVAL = 2

    def __init__(
        self,
        requester=None,
        plugin=None,
        pluginargs=None,
        weight=1,
        signal=None,
        logger=None,
        id=0,
    ):
        self.plugin = plugin
        self._weight = weight
        self.pluginargs = pluginargs
        self.requester = requester
        self.queue = SimpleQueue()
        self.signal = signal
        self.cancelled = False
        self.logger = logger
        self.id = id

    @property
    def weight(self):
        if self.cancelled:
            return 0
        return self._weight

    def init_plugin(self):
        plugin_err = ""
        mod = None
        try:
            mod = importlib.import_module(f".plugins.{self.plugin}", package='captaincredz')
        except:
            plugin_err = traceback.format_exc()
        if mod is None:
            self.logger.error(
                f"[{self.plugin}] Plugin could not be loaded. Exception was caught, stacktrace printed below for debugging purposes:\n"
                + plugin_err
            )
            return False

        self._plugin = None
        try:
            self._plugin = mod.Plugin(self.requester, self.pluginargs)
        except:
            plugin_err = traceback.format_exc()
        if self._plugin is None:
            self.logger.error(
                f"[{self.plugin}] Plugin could not be instanciated! Exception was caught, stacktrace printed below for debugging purposes:\n"
                + plugin_err
            )
            return False

        try:
            valid_args, plugin_err = self._plugin.validate()
        except:
            valid_args, plugin_err = False, traceback.format_exc()
        if not valid_args:
            self.logger.error(
                f"[{self.plugin}] Invalid plugin arguments! The plugin error is: "
                + plugin_err
            )
            return False

        useragent = self.requester.get_random_ua()
        connect_status = False
        try:
            self.logger.debug(f"[{self.plugin}] Testing network connection...")
            connect_status = self._plugin.testconnect(useragent)
            self.logger.debug(f"[{self.plugin}] Plugin test connection successful!")
        except:
            plugin_err = traceback.format_exc()
        if not connect_status:
            self.logger.error(
                f"[{self.plugin}] Plugin test connection failed! The plugin error is: "
                + plugin_err
            )
            return False

        return valid_args and connect_status

    def add(self, username, password):
        self.queue.put((username, password))

    def execute(self, username, password):
        useragent = self.requester.get_random_ua()
        data = dict()
        try:
            data = self._plugin.test_authenticate(username, password, useragent)
        except:
            data["error"] = True
            data["output"] = (
                f"Unhandled exception in the {self.plugin} plugin caught by the worker. This is handled properly, do not worry, the pair of credz will be retried at the end. Stacktrace is printed for debug purposes only:\n"
                + traceback.format_exc()
                + "\nAgain, do not worry, this error is being handled properly and the stacktrace is here for debugging purposes only."
            )
        data["ts"] = datetime.datetime.now().timestamp()
        try:
            self.signal(username, password, data, self.id)
        except Exception as ex:
            self.logger.error(
                "Core error. This is very bizarre and should not happen, please create an issue with the following stacktrace:"
            )
            self.logger.error(str(ex.__repr__()))
            raise ex

    def main(self):
        while not self.cancelled:
            up = None
            try:
                up = self.queue.get(timeout=Worker.SLEEP_INTERVAL)
            except:
                pass
            if up is not None and not self.cancelled:
                u, p = up
                self.execute(u, p)
