import zmq
import time
import json
import random
import sys
import os
import logging

TIMER_ADDRESS = f"ipc:///tmp/{os.environ.get('INSTANCE_NAME', 'captaincredz')}_timer.ipc"
STORAGE_ADDRESS = f"ipc:///tmp/{os.environ.get('INSTANCE_NAME', 'captaincredz')}_storage.ipc"
SPRAYER_ADDRESS = f"ipc:///tmp/{os.environ.get('INSTANCE_NAME', 'captaincredz')}_sprayer.ipc"
PLUGIN_ADDRESS = f"ipc:///tmp/{os.environ.get('INSTANCE_NAME', 'captaincredz')}_plugin.ipc"

# Default configs, will be overwritten if /metadata/config.json exists
delay_request = 10
delay_user = 100
jitter = 2
plugin_name = ""

log_formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
logging.basicConfig(
    stream=sys.stdout, 
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    force=True # Just in case another imported module messed with the root handler
)

is_debug = os.environ.get("DEBUG", "").lower() in ["true", "1", "on", "yes", "y"]
log_level = logging.DEBUG if is_debug else logging.INFO
logger = logging.getLogger("SPRAYER")
logger.setLevel(log_level)
logger.propagate = False
logger.handlers.clear()

stdout_handler = logging.StreamHandler(sys.stdout)
file_handler = logging.FileHandler(os.environ.get("LOG_FILE", "/metadata/captaincredz.log"))

stdout_handler.setFormatter(log_formatter)
file_handler.setFormatter(log_formatter)

logger.addHandler(stdout_handler)
logger.addHandler(file_handler)

def read_json_config(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def read_list_file(filepath):
    try:
        with open(filepath, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []

def send_req(socket, message):
    """Helper to send a REQ message and return the REP string."""
    socket.send_string(message)
    return socket.recv_string()

def run_plugin(plugin, pluginargs, post_actions, username, password, useragent):
    """
    Plugin execution function that delegates to a ZeroMQ worker.
    Returns a valid result type: ('success', 'potential', 'failure', 'inexistant', 'BUG')
    along with an output message.
    """
    # Create a REQ socket for this request
    _context = zmq.Context()
    socket = _context.socket(zmq.REQ)
    socket.connect(PLUGIN_ADDRESS)
    
    # Valid statuses as defined in your requirements
    valid_statuses = {'success', 'potential', 'failure', 'inexistant', 'BUG'}
    
    try:        
        # 1. Prepare and send the payload
        payload = {
            "plugin": plugin,
            "pluginargs": pluginargs,
            "post_actions": post_actions,
            "username": username,
            "password": password,
            "useragent": useragent
        }
        socket.send_json(payload)

        response = socket.recv_json()

        status = response.get("status", "BUG")
        message = response.get("message", "No message provided by worker")

        if status not in valid_statuses:
            return "BUG", f"Invalid status '{status}' received. Must be one of {valid_statuses}"
        return status, message

    except zmq.ZMQError as e:
        return "BUG", f"ZeroMQ networking error: {str(e)}"
    except Exception as e:
        return "BUG", f"Unexpected error during plugin execution: {str(e)}"
    finally:
        socket.close()


def main():
    global delay_request, delay_user, jitter, plugin_name

    context = zmq.Context.instance()

    # Setup REQ sockets to communicate with Timer and Storage
    timer_socket = context.socket(zmq.REQ)
    timer_socket.connect(TIMER_ADDRESS)

    storage_socket = context.socket(zmq.REQ)
    storage_socket.connect(STORAGE_ADDRESS)

    rep_socket = context.socket(zmq.REP)
    rep_socket.bind(SPRAYER_ADDRESS)

    logger.info(f"Started")

    # 1. Configure timer process from /metadata/ww_config.json
    ww_config = read_json_config('/metadata/ww_config.json')
    if ww_config:
        resp = send_req(timer_socket, f"change_config {json.dumps(ww_config)}")
        logger.debug(f"Timer config update: {resp}")

    # 2. Send content of .lst files to storage process
    source_files = [
        ('username', '/metadata/usernames.lst'),
        ('password', '/metadata/passwords.lst'),
        ('userpass', '/metadata/userpass.lst')
    ]
    for src_type, filepath in source_files:
        for item in read_list_file(filepath):
            if len(item.strip()) > 0:
                send_req(storage_socket, f"insert_source {src_type} {item.strip()}")
    logger.debug("Storage populated with source lists.")

    # 3. Configure delays and plugin locally from /metadata/config.json
    local_config = read_json_config('/metadata/config.json')
    delay_request = local_config.get('delay_request', delay_request)
    delay_user = local_config.get('delay_user', delay_user)
    jitter = local_config.get('jitter', jitter)
    post_actions = local_config.get('post_actions', jitter)
    plugin_name = local_config.get('plugin')["name"]
    pluginargs = local_config.get('plugin')["args"]
    useragents = local_config.get('plugin')["useragents"]

    # 4. Send init_delays to storage process
    resp = send_req(storage_socket, f"init_delays {delay_user} {TIMER_ADDRESS}")
    logger.debug(f"Init delays: {resp}")

    # 5. Main Loop / Listen for ZeroMQ messages
    is_ready_to_request = True 

    while True:
        # If we are waiting for the sleep_request_over signal from the timer
        if not is_ready_to_request:
            msg = rep_socket.recv_string()
            rep_socket.send_string('ok')
            logger.debug(f"Received: {msg}")
            if msg == "sleep_request_over":
                is_ready_to_request = True

        if is_ready_to_request:
            logger.debug(f"Ready to request")
            resp = send_req(storage_socket, "get_next_candidate")
            
            if resp == "!!FINISHED":
                logger.info("All candidates exhausted. Stopping sprayer.")
                break
            
            elif resp == "!!WAIT":
                time.sleep(1)
                logger.debug(f"Waiting, no user ready")
                continue
            
            else:
                # We received credentials
                username, password = resp.split('#CAPTAIN#', 1)
                logger.debug(f"Spraying {username} : {password}")
                
                # Attempt to spray with credentials, retrying up to 3 times on BUG
                attempts = 0
                result = "BUG"
                output = ""
                useragent = ""
                
                while attempts < 3 and result == "BUG":
                    useragent = random.choice(useragents)
                    result, output = run_plugin(plugin_name, pluginargs, post_actions, username, password, useragent)
                    if result == "BUG":
                        attempts += 1
                        logger.debug(f"Plugin bug encountered for {username}. Retry {attempts}/3...")
                        time.sleep(1)
                    else:
                        break
                
                if result == "BUG":
                    logger.error("Fatal: Plugin returned BUG 3 times. Crashing.")
                    sys.exit(1)
                
                # Calculate randomized request delay
                actual_request_delay = max(0, delay_request + random.uniform(0, jitter))
                actual_user_delay = max(0, delay_user + random.uniform(0, jitter))

                send_req(timer_socket, f"register_event 'sleep_request_over' {SPRAYER_ADDRESS} {actual_request_delay:.2f}")

                payload = json.dumps({
                    "username": username,
                    "password": password,
                    "useragent": useragent,
                    "plugin": plugin_name,
                    "result": result,
                    "output": output
                })

                logger.info(f"[{plugin_name}] {result.upper()} {username}:{password} -- {output}")
                
                send_req(storage_socket, f"insert_result {payload}")

                send_req(storage_socket, f"ready no {username}")

                send_req(timer_socket, f"register_event 'ready yes {username}' {STORAGE_ADDRESS} {actual_user_delay:.2f}")

                # Suspend spraying until 'sleep_request_over' is pushed back to us by the Timer
                is_ready_to_request = False

if __name__ == "__main__":
    try:
        # Wait for everything to start
        time.sleep(1)
        main()
    except KeyboardInterrupt:
        logger.info("\nShutting down sprayer.")