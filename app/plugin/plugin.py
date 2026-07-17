import zmq
import importlib
import requests
import sys
import traceback
import logging
import os
import random
import requests

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)

logging.basicConfig(
    stream=sys.stdout, 
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    force=True # Just in case another imported module messed with the root handler
)

is_debug = os.environ.get("DEBUG", "").lower() in ["true", "1", "on", "yes", "y"]
log_level = logging.DEBUG if is_debug else logging.INFO
logger = logging.getLogger("PLUGIN")
logger.setLevel(log_level)

class Requester:
    def __init__(self, proxy=None, headers=None, req_timeout=60):
        self.proxy = {"http": proxy, "https": proxy}
        self.headers = headers
        self.request_timeout = req_timeout

    def patch_kwargs(self, dico):
        if self.headers is not None:
            for h in self.headers:
                v = self.headers[h]
                if "headers" in dico:
                    dico["headers"][h] = v
                else:
                    dico["headers"] = {h: v}
        dico["proxies"] = self.proxy
        if not "verify" in dico:
            dico["verify"] = False
        if not "timeout" in dico:
            dico["timeout"] = self.request_timeout
        return dico

    def delete(self, *args, **kwargs):
        kwargs = self.patch_kwargs(kwargs)
        return requests.delete(*args, **kwargs)

    def get(self, *args, **kwargs):
        kwargs = self.patch_kwargs(kwargs)
        return requests.get(*args, **kwargs)

    def head(self, *args, **kwargs):
        kwargs = self.patch_kwargs(kwargs)
        return requests.head(*args, **kwargs)

    def options(self, *args, **kwargs):
        kwargs = self.patch_kwargs(kwargs)
        return requests.options(*args, **kwargs)

    def patch(self, *args, **kwargs):
        kwargs = self.patch_kwargs(kwargs)
        return requests.patch(*args, **kwargs)

    def post(self, *args, **kwargs):
        kwargs = self.patch_kwargs(kwargs)
        return requests.post(*args, **kwargs)

    def put(self, *args, **kwargs):
        kwargs = self.patch_kwargs(kwargs)
        return requests.put(*args, **kwargs)

    def request(self, *args, **kwargs):
        kwargs = self.patch_kwargs(kwargs)
        return requests.request(*args, **kwargs)

    def Session(self):
        s = requests.Session()
        s.proxies.update(self.proxy)
        if self.headers is not None:
            dico = dict()
            for h in self.headers:
                v = self.headers[h]
                dico[h] = v
            s.headers.update(dico)
        s.verify = False
        return s

    def session(self):
        # Alias for backwards compatibility (until all plugins have migrated to Session())
        return self.Session()

def main():
    # 1. Initialize ZeroMQ context and socket
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"ipc:///tmp/{os.environ.get('INSTANCE_NAME', 'captaincredz')}_plugin.ipc")
    plugins = dict()

    logger.info("Worker started")

    while True:
        try:
            # 3. Wait for the next request from the client
            payload = socket.recv_json()
            
            plugin_name = payload.get("plugin")
            pluginargs = payload.get("pluginargs", {"url": "http://127.0.0.1"})
            post_actions = payload.get("post_actions", dict())
            username = payload.get("username")
            password = payload.get("password")
            ua = payload.get("useragent")

            proxy = pluginargs.get("proxy")
            headers = pluginargs.get("headers")
            
            if not all([plugin_name, username, password, ua]):
                socket.send_json({"status": "BUG", "message": "Missing required fields (plugin, username, password, useragent)", "useragent": ua})
                continue


            plugin_instance = None

            if plugin_name in plugins.keys():
                plugin_instance = plugins[plugin_name]
            else:
                logger.info(f"Loading plugin '{plugin_name}'...")
                try:
                    # This assumes the directory structure is: plugins/test/__init__.py
                    plugin_module = importlib.import_module(f"plugins.{plugin_name}")
                    plugin_class = getattr(plugin_module, "Plugin")
                except ModuleNotFoundError:
                    socket.send_json({"status": "BUG", "message": f"Plugin '{plugin_name}' not found.", "useragent": ua})
                    continue
                except AttributeError:
                    socket.send_json({"status": "BUG", "message": f"Plugin '{plugin_name}' missing 'Plugin' class.", "useragent": ua})
                    continue
                # 5. Instantiate and Validate
                plugin_instance = plugin_class(requester=Requester(proxy=proxy, headers=headers), pluginargs=pluginargs)
                plugins[plugin_name] = plugin_instance
                is_valid, err_msg = plugin_instance.validate()
            
                if not is_valid:
                    socket.send_json({"status": "BUG", "message": f"Plugin validation failed: {err_msg}", "useragent": ua})
                    continue

            # 6. Execute authentication test
            result_data = plugin_instance.test_authenticate(username, password, ua)

            # 7. Map the plugin's response back to the ZMQ client format
            if result_data.get("error"):
                # If error is True, we map this to your 'BUG' status
                status = "BUG"
                message = result_data.get("output", "Unknown error during plugin execution")
            else:
                # Otherwise, grab the success/failure/inexistant/potential string
                status = result_data.get("result", "BUG")
                message = result_data.get("output", "")
            
            for pa in post_actions:
                if status.lower() in [x.lower() for x in post_actions[pa].get("triggers")]:
                    try:
                        action = importlib.import_module(f"post_actions.{pa}")
                        action.action(username, password, result_data.get("response"), plugin_name, status, post_actions[pa].get("params"))
                    except Exception as e:
                        raise e
                        self._logger.error(
                            f"Post-action module {pa} cannot be imported: directory does not exist."
                        )

            # 8. Send the result back to the client
            socket.send_json({"status": status, "message": message, "useragent": result_data.get("useragent", ua)})

        except KeyboardInterrupt:
            logger.debug("\nShutting down worker gracefully...")
            break
        except Exception as e:
            logger.error(f"\nCritical Worker Error: {e}")
            traceback.print_exc()
            # If the socket is holding a lock expecting a reply, free it up with an error message
            try:
                socket.send_json({"status": "BUG", "message": f"Worker crash exception: {str(e)}", "useragent": None})
            except Exception:
                pass

    # Cleanup
    socket.close()
    context.term()

if __name__ == "__main__":
    main()