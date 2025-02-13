import json
import os
import threading
import signal
import sys
import importlib
from pprint import pprint
from .cache import Cache
from .logger import Logger
from .pool import Pool
from .requester import Requester
from .worker import Worker


class Engine:
    def __init__(self, args):
        self._logger = None
        self._stopped = False
        self._progress_bar = None
        self._post_actions = dict()
        self._workers = [] # One worker per plugin instance
        default_args = {
            "plugins": None,
            "post_actions": None,
            "userfile": None,
            "passwordfile": None,
            "userpassfile": None,
            "jitter": 0,
            "delay_req": 0,
            "delay_user": 0,
            "chunk_size": 0,
            "chunk_delay": 0,
            "stop_on_success": False,
            "stop_worker_on_success": False,
            "log_file": "captaincredz.log",
            "cache_file": "cache.db",
            "verbose": False,
            "weekday_warrior": None,
        }
        plugin_default_args = {
            "args": [],
            "headers": dict(),
            "proxy": None,
            "useragentfile": None,
            "weight": 1,
            "req_timeout": 60,
        }

        self.args = {**default_args, **args.__dict__}
        if self.args["config"] != None:
            try:
                with open(self.args["config"], "r") as f:
                    j = json.load(f)
                    for k in j:
                        if j[k] is not None:
                            self.args[k] = j[k]
            except:
                print("The main config file cannot be loaded, aborting")
                self._valid_args = False
                return
        if self.args["weekday_warrior"] != None:
            try:
                with open(self.args["weekday_warrior"], "r") as f:
                    self.args["weekday_warrior"] = json.load(f)
            except:
                print("The weekday warrior config file cannot be loaded, aborting")
                self._valid_args = False
                return

        self._logger = Logger(self.args["log_file"], verbose=self.args["verbose"])
        self._valid_args = self.check_args()
        if not self._valid_args:
            return

        # Initialize post-actions
        if self.args["post_actions"] is not None:
            for action_name in self.args["post_actions"].keys():
                action = self.args["post_actions"][action_name]
                for hook in action["trigger"]:
                    if hook not in self._post_actions.keys():
                        # If hook does not exist in the post_action dict, we create it
                        self._post_actions[hook] = []

                    # In any case, we add the current action to the list associated with the hook being processed
                    d = {
                        "module": importlib.import_module(
                            f".post_actions.{action_name}",
                            package='captaincredz'
                        ),
                        "params": action.get("params"),
                        "name": action_name,
                    }
                    self._post_actions[hook].append(d)

        # Initialize plugins
        for i in range(len(self.args["plugins"])):
            for k in plugin_default_args:
                if not k in self.args["plugins"][i].keys():
                    self.args["plugins"][i][k] = plugin_default_args[k]
        for p in self.args["plugins"]:
            requests_proxy = Requester(
                useragentfile=p["useragentfile"],
                proxy=p["proxy"],
                headers=p["headers"],
                req_timeout=p["req_timeout"],
            )
            w = Worker(
                requests_proxy,
                p["name"],
                p["args"],
                p["weight"],
                self.handle_worker_response,
                self._logger,
                len(self._workers),
            )
            valid = w.init_plugin()
            if valid:
                self._workers.append(w)
            else:
                self._valid_args = False
                return

        # Initialize cache
        self._cache = Cache(self.args["cache_file"])
        if self._cache.error is not None:
            self._logger.error(self._cache.error)
            self._valid_args = False
            return

        delays = {
            "req": self.args["delay_req"],
            "jitter": self.args["jitter"],
            "user": self.args["delay_user"],
            "chunk_delay": self.args["chunk_delay"],
            "chunk_size": self.args["chunk_size"],
            "ww": self.args["weekday_warrior"],
        }
        self._pool = Pool(
            self.args["userfile"],
            self.args["passwordfile"],
            self.args["userpassfile"],
            delays,
            self._cache,
            self._workers,
            self._logger,
        )

    def check_args(self):
        if self.args["plugins"] is None:
            self._logger.error("At least 1 plugin must be specified")
            return False
        if type(self.args["plugins"]) != list:
            self._logger.error(
                "Your plugins format is weird, it must be a list of objects with attributes 'name' (and optionally 'weight', 'headers', 'args', 'proxy' and 'useragentfile')"
            )
            return False
        if self.args["userfile"] is None and self.args["userpassfile"] is None:
            self._logger.error(
                "At least a userfile or a userpassfile must be specified"
            )
            return False
        if self.args["userfile"] is not None and self.args["passwordfile"] is None:
            self._logger.error(
                "A passwordfile must be specified along with the userfile"
            )
            return False
        for f in ["userfile", "userpassfile", "passwordfile"]:
            if self.args[f] is not None and (
                not os.path.isfile(self.args[f]) or not os.access(self.args[f], os.R_OK)
            ):
                self._logger.error(f"The {f} ({self.args[f]}) cannot be accessed.")
                return False
        for p in ["jitter", "delay_req", "delay_user", "chunk_size", "chunk_delay"]:
            if type(self.args[p]) != int:
                self._logger.error(
                    f"Parameter {p} must be specified, and must be an integer"
                )
                return False
        if self.args["weekday_warrior"] is not None:
            for x in [
                "utc_offset",
                "daily_speedup",
                "initial_speed",
                "hours_factor",
                "days_factor",
            ]:
                if not x in self.args["weekday_warrior"].keys():
                    self._logger.error(
                        f"Key {x} should be present in weekday warrior file."
                    )
                    return False
        if self.args["post_actions"] is not None:
            for action_name in self.args["post_actions"].keys():
                action = self.args["post_actions"][action_name]
                try:
                    importlib.import_module(f".post_actions.{action_name}", package='captaincredz')
                except Exception as e:
                    raise e
                    self._logger.error(
                        f"Post-action module {action_name} cannot be imported: directory does not exist."
                    )
                    return False
                for hook in action["trigger"]:
                    if hook not in Cache.TRANSLATE and not hook == "error":
                        self._logger.error(
                            f"Hook '{hook}' for post-action {action_name} is not correct. "
                            f"Must be either 'error', 'success', 'potential', 'failure' or 'inexistant'."
                        )
                        return False
        return True

    def start(self, progress_bar=None):
        if not self._valid_args:
            if self._logger is not None:
                self._logger.error("Arguments are not valid (see above). Exiting!")
            else:
                print("Arguments are not valid (see above). Exiting!")
            return

        signal.signal(signal.SIGINT, self.sighandler)

        if progress_bar is not None:
            self._progress_bar = progress_bar
            self._progress_task = self._progress_bar.add_task(
                "[red]Spraying...", total=self._pool.get_total_size()
            )

        self._worker_threads = []
        for w in self._workers:
            t = threading.Thread(target=w.main)
            t.start()
            self._worker_threads.append(t)

        while not self._stopped:
            workers = [_w for _w in self._workers if not _w.cancelled]
            userpass, w_id = self._pool.get_creds(workers)
            if userpass is None:
                self._logger.info("No more creds to test")
                self._stopped = True
            else:
                self._logger.debug(f"Current candidate is {userpass}")
                workers[w_id].add(userpass["username"], userpass["password"])
        self._cache.write_back()
        for w in self._workers:
            w.cancelled = True
        self._pool.stop()
        for t in self._worker_threads:
            t.join()

        self._logger.debug("All workers have successfully stopped")

    def sighandler(self, signum, frame):
        # print(signum, frame)
        if not self._stopped:
            self._logger.info("Stopping gracefully, please wait...")
            self._stopped = True
            self._pool.stop()
            for w in self._workers:
                w.cancelled = True
            self._cache.write_back()
            self._logger.info(
                "All cleaned up! Just waiting for workers to finish their current tasks, you may kill them with another CTRL+C if it is taking too long"
            )
            sys.exit()
        else:
            self._logger.info(
                "Double CTRL+C, hard quitting! You may have to press CTRL+C once more..."
            )
            sys.exit()

    def handle_worker_response(self, u, p, data, plugin_id):
        # data contains "ts", "result", "error", "request", "output"
        self._pool.signal_tried(u, p, plugin_id, error=data["error"])
        if data["error"]:
            data["result"] = None
            if "error" in self._post_actions.keys():
                for pa_dict in self._post_actions["error"]:
                    pa = pa_dict["module"]
                    params = pa_dict.get("params")
                    try:
                        pa.action(
                            u,
                            p,
                            data["ts"],
                            data["request"],
                            self._workers[plugin_id].plugin,
                            data["result"],
                            self._logger,
                            action_params=params,
                        )
                    except Exception as ex:
                        self._logger.error(
                            f"The post_action {pa_dict.get('name')} (trigger error) raised the following exception:"
                        )
                        self._logger.error(str(ex.__repr__()))
                        self._logger.error(f"Ignoring and continuing spray.")
        self._logger.log_tentative(
            u,
            p,
            data["ts"],
            data["result"],
            data["output"],
            self._workers[plugin_id].plugin,
        )
        if not data["error"]:
            self._cache.add_tentative(
                u,
                p,
                data["ts"],
                data["result"],
                data["output"],
                self._workers[plugin_id].plugin,
            )

            # If no post-actions were defined, this key will be empty, therefore we need to check first
            if data["result"] in self._post_actions.keys():
                # Calling the right post-action hooks
                for pa_dict in self._post_actions[data["result"]]:
                    pa = pa_dict["module"]
                    params = pa_dict.get("params")
                    try:
                        pa.action(
                            u,
                            p,
                            data["ts"],
                            data["request"],
                            self._workers[plugin_id].plugin,
                            data["result"],
                            self._logger,
                            action_params=params,
                        )
                    except Exception as ex:
                        self._logger.error(
                            f"The post_action {pa_dict.get('name')} (trigger {data['result']}) raised the following exception:"
                        )
                        self._logger.error(str(ex.__repr__()))
                        self._logger.error(f"Ignoring and continuing spray.")
            # Handling specific cases
            # If it is a success
            if data["result"] == Cache.TRANSLATE_INV[Cache.RESULT_SUCCESS]:
                if self.args["stop_on_success"]:
                    self._logger.info(
                        "Stopping on first success according to configuration option stop_on_success"
                    )
                    self.sighandler(0, 0)
                if self.args["stop_worker_on_success"]:
                    self._logger.info(
                        f"Stopping plugin {self._workers[plugin_id].plugin} (plugin_id = {plugin_id}) on first success according to configuration option stop_worker_on_success"
                    )
                    self._workers[plugin_id].cancelled = True
                self._pool.trim_user(u, plugin_id)
                self._cache.write_back()
                if self._progress_bar is not None:
                    self._progress_bar.update(
                        self._progress_task,
                        completed=self._pool.attempts_count,
                        total=self._pool.get_total_size() + self._pool.attempts_count,
                    )
            # If it does not exist
            elif data["result"] == Cache.TRANSLATE_INV[Cache.RESULT_INEXISTANT]:
                self._pool.trim_user(u, plugin_id)
                if self._progress_bar is not None:
                    self._progress_bar.update(
                        self._progress_task,
                        completed=self._pool.attempts_count,
                        total=self._pool.get_total_size() + self._pool.attempts_count,
                    )
            elif self._progress_bar is not None:
                self._progress_bar.update(
                    self._progress_task, completed=self._pool.attempts_count
                )

        if self._stopped:
            self._cache.write_back()
