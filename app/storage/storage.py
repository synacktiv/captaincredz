import sqlite3
import zmq
import json
import datetime
from collections import Counter
import os
import logging
import sys

logging.basicConfig(
    stream=sys.stdout, 
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    force=True # Just in case another imported module messed with the root handler
)

is_debug = os.environ.get("DEBUG", "").lower() in ["true", "1", "on", "yes", "y"]
log_level = logging.DEBUG if is_debug else logging.INFO
logger = logging.getLogger("STORAGE")
logger.setLevel(log_level)

class StorageNode:
    def __init__(self, db_path='/metadata/storage.db'):
        self.db_path = db_path
        
        # In-memory set to track potential next candidates
        self.rested_users = set()
        
        self._init_db()
        # TODO check if users are rested enough (check with sprayer config)

    def _init_db(self):
        """Initializes the SQLite database with the required tables and constraints."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create sources table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT CHECK(type IN ('username', 'password', 'userpass')) NOT NULL,
                    data TEXT NOT NULL
                )
            ''')
            
            # Create results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    username TEXT,
                    password TEXT,
                    useragent TEXT,
                    plugin TEXT,
                    result TEXT CHECK(result IN ('success', 'potential', 'failure', 'inexistant')) NOT NULL,
                    output TEXT
                )
            ''')
            conn.commit()

    def run(self):
        """Starts the ZeroMQ listener loop."""
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind(f"ipc:///tmp/{os.environ.get('INSTANCE_NAME', 'captaincredz')}_storage.ipc")
        
        logger.info(f"Storage node active")
        logger.debug("SQLite DB: '{self.db_path}' - Waiting for messages...")
        
        while True:
            # Wait for next request from client
            message = socket.recv_string()
            
            try:
                response = self._handle_message(message)
            except Exception as e:
                response = f"error: internal server error - {str(e)}"
                
            # Send reply back to client
            socket.send_string(response)
    
    def _get_missing_pairs(self):
        """
        Uses a CTE to generate all possible user/pass combinations from sources,
        filters out users that are already 'success' or 'inexistant',
        and returns the ones that do not have a matching result yet.
        """
        query = '''
            WITH all_pairs AS (
                -- Part 1: Handle 'userpass' (Assigned Priority 1 so it always comes first)
                SELECT 
                    1 AS priority,
                    id AS u_id,
                    id AS p_id,
                    substr(data, 1, instr(data, ':') - 1) AS username, 
                    substr(data, instr(data, ':') + 1) AS password 
                FROM sources 
                WHERE type = 'userpass' AND instr(data, ':') > 0
            
                UNION ALL 
                
                -- Part 2: Handle split 'username' and 'password' (Assigned Priority 2)
                SELECT 
                    2 AS priority,
                    u.id AS u_id, 
                    p.id AS p_id, 
                    u.data AS username, 
                    p.data AS password 
                FROM sources u 
                JOIN sources p ON u.type = 'username' AND p.type = 'password'
            )
            SELECT ap.username, ap.password
            FROM all_pairs ap
            LEFT JOIN results r ON ap.username = r.username AND ap.password = r.password
            WHERE r.id IS NULL
            AND ap.username NOT IN (
                SELECT username FROM results WHERE result IN ('success', 'inexistant')
            )
            ORDER BY ap.priority ASC, ap.u_id ASC, ap.p_id ASC;
        '''
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def _handle_message(self, message):
        """Parses and acts upon incoming ZeroMQ messages."""
        parts = message.strip().split(' ', 2)
        if not parts:
            return "error: empty message"
            
        command = parts[0].lower()
        logger.debug(f"Received {command}")
        
        # --- Handle 'get_next_candidate' ---
        if command == 'get_next_candidate':
            missing_pairs = self._get_missing_pairs()
            
            # If all possible pairs have an associated result
            if not missing_pairs:
                return "!!FINISHED"
            
            # If there are missing pairs, but no users are currently rested
            if not self.rested_users:
                return "!!WAIT"
                
            # Filter missing pairs to only include users that are currently rested
            rested_missing = [(u, p) for u, p in missing_pairs if u in self.rested_users]
            
            if not rested_missing:
                return "!!WAIT"
                
            # Count the number of missing pairs for each rested user
            user_counts = Counter(u for u, p in rested_missing)
            
            # Get the user with the highest count of missing pairs
            # most_common(1) returns a list like: [('admin', 15)]
            target_user = user_counts.most_common(1)[0][0]
            
            # Return the first available password for our target user
            for username, password in rested_missing:
                if username == target_user:
                    return f"{username} {password}"
            
            # If we reach here, there are missing pairs, but none belong to the currently rested users
            return "!!WAIT"
            
        # --- Handle 'ready' state for rested_users ---
        elif command == 'ready':
            if len(parts) < 3:
                return "error: invalid ready command format. Use 'ready [yes/no] <username>'"
            
            action = parts[1].lower()
            username = parts[2]
            
            if action == 'yes':
                self.rested_users.add(username)
                return f"ok: '{username}' added to rested_users."
            elif action == 'no':
                self.rested_users.discard(username)
                return f"ok: '{username}' removed from rested_users."
            else:
                return "error: action must be 'yes' or 'no'"
                
        # --- Handle inserts ---
        elif command == 'insert_source':
            if len(parts) < 3:
                return "error: use 'insert_source <type> <data>'"
            return self._db_insert('sources', type=parts[1], data=parts[2])

        elif command == 'insert_result':
            if len(parts) < 2:
                return "error: use 'insert_result <json_payload>'"
            try:
                payload = json.loads(parts[1] + (f" {parts[2]}" if len(parts) > 2 else ""))
                return self._db_insert(
                    'results', 
                    username=payload.get('username'), 
                    password=payload.get('password'), 
                    useragent=payload.get('useragent'),
                    plugin=payload.get('plugin'), 
                    result=payload.get('result'), 
                    output=payload.get('output')
                )
            except json.JSONDecodeError:
                return "error: invalid JSON payload"
        # --- Handle 'init_delays' ---
        elif command == 'init_delays':
            if len(parts) < 3:
                return "error: use 'init_delays <delay_time> <zeromq_address>'"
            
            try:
                delay_time = float(parts[1])
                zmq_address = parts[2]
            except ValueError:
                return "error: delay_time must be a valid number"
            
            # First, set all users as rested
            # Query all unique usernames and their single most recent result timestamp
            query = '''
                SELECT data AS username FROM sources WHERE type = 'username'
                UNION
                SELECT substr(data, 1, instr(data, ':') - 1) AS username 
                FROM sources WHERE type = 'userpass' AND instr(data, ':') > 0
            '''
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                usernames = cursor.fetchall()
            for u in usernames:
                logger.debug(f"Initializing {u[0]} as rested")
                self.rested_users.add(u[0])
            
            # Query all unique usernames and their single most recent result timestamp
            query = '''
                WITH all_users AS (
                    SELECT data AS username FROM sources WHERE type = 'username'
                    UNION
                    SELECT substr(data, 1, instr(data, ':') - 1) AS username 
                    FROM sources WHERE type = 'userpass' AND instr(data, ':') > 0
                )
                SELECT u.username, MAX(r.timestamp)
                FROM all_users u
                JOIN results r ON u.username = r.username
                GROUP BY u.username
            '''
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                user_timestamps = cursor.fetchall()

            now = datetime.datetime.now(datetime.timezone.utc)
            delayed_count = 0

            ctx = zmq.Context.instance()
            event_socket = ctx.socket(zmq.REQ) 
            event_socket.connect(zmq_address)
            
            for username, last_ts_str in user_timestamps:
                self.rested_users.add(username)
                if not last_ts_str:
                    continue  # User has no results yet, no delay needed
                    
                # Parse SQLite's default CURRENT_TIMESTAMP format (YYYY-MM-DD HH:MM:SS)
                try:
                    last_ts = datetime.datetime.strptime(last_ts_str, '%Y-%m-%d %H:%M:%S')
                    last_ts = last_ts.replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    continue
                    
                time_diff = (now - last_ts).total_seconds()
                
                # Check if the latest result is too close to the current time
                if time_diff < delay_time:
                    next_delay = delay_time - time_diff
                    
                    # Remove from rested_users
                    logger.debug(f"Latest attempt for {username} is too recent, removing from rested")
                    self.rested_users.discard(username)
                    
                    # Send the registration event
                    event_msg = f"register_event 'ready yes {username}' ipc:///tmp/{os.environ.get('INSTANCE_NAME', 'captaincredz')}_storage.ipc {next_delay:.2f}"
                    event_socket.send_string(event_msg)
                    event_socket.recv_string()
                    
                    delayed_count += 1
            event_socket.close()
            
            return f"ok: initialized delays, suspended {delayed_count} users"

        return f"error: unknown command '{command}'"

    def _db_insert(self, table, **kwargs):
        """Helper to safely insert rows into SQLite, preventing exact duplicates."""
        columns = ', '.join(kwargs.keys())
        placeholders = ', '.join(['?'] * len(kwargs))
        values = tuple(kwargs.values())
        
        # Build the WHERE clauses for the duplication check dynamically
        where_clauses = ' AND '.join([f"{k} = ?" for k in kwargs.keys()])
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if the exact row already exists
                cursor.execute(f"SELECT 1 FROM {table} WHERE {where_clauses}", values)
                if cursor.fetchone():
                    return f"ok: row already exists in {table}, skipping insert"
                
                # If it doesn't exist, proceed with the insert
                cursor.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
                conn.commit()
            return f"ok: inserted into {table}"
        except sqlite3.IntegrityError as e:
            return f"error: database constraint failed - {str(e)}"

if __name__ == "__main__":
    node = StorageNode()
    try:
        node.run()
    except KeyboardInterrupt:
        logger.info("\nShutting down storage node.")