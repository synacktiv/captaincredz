import zmq
import time
import datetime
import json
import shlex
import heapq
import collections.abc
import os
import logging
import sys

# 1. Default Configuration
config = {
    "utc_offset": 0,
    "daily_speedup": 1,
    "initial_speed": 1,
    "hours_factor": {
        "0": 1, "1": 1, "2": 1, "3": 1, "4": 1, "5": 1, "6": 1, "7": 1,
        "8": 1, "9": 1, "10": 1, "11": 1, "12": 1, "13": 1, "14": 1, "15": 1,
        "16": 1, "17": 1, "18": 1, "19": 1, "20": 1, "21": 1, "22": 1, "23": 1
    },
    "days_factor": {
        "mon": 1, "tue": 1, "wed": 1, "thu": 1, "fri": 1, "sat": 1, "sun": 1
    }
}

logging.basicConfig(
    stream=sys.stdout, 
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    force=True # Just in case another imported module messed with the root handler
)

is_debug = os.environ.get("DEBUG", "").lower() in ["true", "1", "on", "yes", "y"]
log_level = logging.DEBUG if is_debug else logging.INFO
logger = logging.getLogger("TIMER")
logger.setLevel(log_level)

# 2. Helper Functions
def deep_update(d, u):
    """Recursively updates a nested dictionary so partial configs don't overwrite entire sub-dicts."""
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def get_current_speed(cfg, start_time):
    """Calculates the current speed multiplier based on real-world time and config."""
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=cfg['utc_offset'])
    hour = str(now.hour)
    day = now.strftime('%a').lower()
    running_days = ((now - start_time).total_seconds()) / (60*60*24)

    speedup_multiplier = 1 + (cfg.get('daily_speedup', 1.0)-1) * running_days
    base = min(cfg.get('initial_speed', 1.0) * speedup_multiplier, 1.0)
    h_factor = min(cfg.get('hours_factor', {}).get(hour, 1.0), 1.0)
    d_factor = min(cfg.get('days_factor', {}).get(day, 1.0), 1.0)

    return base * h_factor * d_factor

# 3. Main Loop
def run_timer():
    context = zmq.Context.instance()
    
    server_socket = context.socket(zmq.REP)
    server_socket.bind(f"ipc:///tmp/{os.environ.get('INSTANCE_NAME', 'captaincredz')}_timer.ipc")
    
    poller = zmq.Poller()
    poller.register(server_socket, zmq.POLLIN)

    events = [] 
    
    virtual_time = 0.0
    last_real_time = time.time()

    start_time = datetime.datetime.now(datetime.timezone.utc)

    logger.info(f"Timer started")

    while True:
        socks = dict(poller.poll(50)) 

        # --- Handle Incoming ZeroMQ Messages ---
        if server_socket in socks:
            msg = server_socket.recv_string()
            try:
                parts = shlex.split(msg)
                if not parts:
                    server_socket.send_string("ERROR: Empty command")
                    continue

                cmd = parts[0]

                logger.debug(f"Received {parts}")
                
                if cmd == "register_event":
                    name = parts[1]
                    addr = parts[2]
                    delay_seconds = float(parts[3])
                    
                    # Calculate the target virtual time
                    trigger_time = virtual_time + delay_seconds
                    heapq.heappush(events, (trigger_time, name, addr))
                    
                    server_socket.send_string(f"OK: Event '{name}' registered. Due in {delay_seconds} virtual seconds.")

                elif cmd == "change_config":
                    # Extract the JSON payload directly after the command
                    json_str = msg.split(maxsplit=1)[1]
                    updates = json.loads(json_str)
                    deep_update(config, updates)
                    
                    server_socket.send_string("OK: Configuration updated.")
                
                else:
                    server_socket.send_string(f"ERROR: Unknown command '{cmd}'")

            except Exception as e:
                server_socket.send_string(f"ERROR: Failed to process command - {str(e)}")

        # --- Update Virtual Time ---
        now_real = time.time()
        delta_real = now_real - last_real_time
        last_real_time = now_real

        current_speed = get_current_speed(config, start_time)
        virtual_time += delta_real * current_speed

        # --- Trigger Due Events ---
        # If the heap is not empty and the earliest event is in the past (virtually)
        while events and events[0][0] <= virtual_time:
            trigger_time, name, addr = heapq.heappop(events)
            
            # Ensure the address has a tcp protocol prefix
            target_addr = addr if addr.startswith("ipc://") else f"ipc://{addr}"
            
            # Fire-and-forget notification to the client
            notif_socket = context.socket(zmq.REQ)
            notif_socket.setsockopt(zmq.LINGER, 500) # Drop message immediately if target is down
            try:
                notif_socket.connect(target_addr)
                notif_socket.send_string(name)
                notif_socket.recv_string()
            except Exception as e:
                logger.error(f"Failed to notify {target_addr}: {e}")
            finally:
                notif_socket.close()
                
            logger.debug(f"Fired event '{name}' to {target_addr} at virtual time {virtual_time:.2f}")

if __name__ == "__main__":
    logger.debug("Running")
    run_timer()