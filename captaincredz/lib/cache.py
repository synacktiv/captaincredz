import os, threading, sqlite3, datetime


class Cache:
    RESULT_SUCCESS = 0
    RESULT_POTENTIAL = 1
    RESULT_FAILURE = 2
    RESULT_INEXISTANT = 3
    TRANSLATE = {
        "success": RESULT_SUCCESS,
        "potential": RESULT_POTENTIAL,
        "failure": RESULT_FAILURE,
        "inexistant": RESULT_INEXISTANT,
    }
    TRANSLATE_INV = {
        RESULT_SUCCESS: "success",
        RESULT_POTENTIAL: "potential",
        RESULT_FAILURE: "failure",
        RESULT_INEXISTANT: "inexistant",
    }
    WRITEBACK_DIFF_THRESHOLD = 5

    def __init__(self, cache_file="cache.db"):
        self.L1 = dict()
        self.lock = threading.Lock()
        self.cache_file = cache_file
        self.error = None
        self.diff = 0
        if os.path.exists(self.cache_file) and not os.path.isfile(self.cache_file):
            self.error = (
                f"The cache path ({self.cache_file}) already exists and is not a file."
            )
        if self.error is None:
            conn = None
            try:
                conn = sqlite3.connect(self.cache_file)
            except:
                self.error = "The cache file cannot be loaded by SQLite."
            if self.error is None:
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache (
                        id INTEGER PRIMARY KEY,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        username TEXT NOT NULL,
                        password TEXT NOT NULL,
                        result INTEGER NOT NULL,
                        output TEXT NOT NULL,
                        plugin TEXT NOT NULL
                    )
                """
                )
                conn.commit()

                # Fill L1 cache
                self.lock.acquire()
                recs = conn.cursor().execute("SELECT * from cache").fetchall()
                for data in recs:
                    id, ts, username, passwd, res, out, plugin = data
                    if not plugin in self.L1:
                        self.L1[plugin] = dict()
                    if not username in self.L1[plugin]:
                        self.L1[plugin][username] = dict()
                    self.L1[plugin][username][passwd] = {
                        "timestamp": ts,
                        "result": res,
                        "output": out,
                        "in_db": True,
                    }
                self.lock.release()

    def write_back(self):
        self.lock.acquire()
        conn = sqlite3.connect(self.cache_file)
        for plugin in self.L1:
            for username in self.L1[plugin]:
                for password in self.L1[plugin][username]:
                    if not self.L1[plugin][username][password]["in_db"]:
                        rec = self.L1[plugin][username][password]
                        conn.cursor().execute(
                            """
                            INSERT INTO cache (
                                timestamp,
                                username,
                                password,
                                result,
                                output,
                                plugin
                            ) VALUES (?,?,?,?,?,?)
                        """,
                            (
                                rec["timestamp"],
                                username,
                                password,
                                rec["result"],
                                rec["output"],
                                plugin,
                            ),
                        )
                        self.L1[plugin][username][password]["in_db"] = True
        conn.commit()
        self.diff = 0
        self.lock.release()

    def add_tentative(self, username, password, timestamp, result, output, plugin):
        if not plugin in self.L1:
            self.L1[plugin] = dict()
        if not username in self.L1[plugin]:
            self.L1[plugin][username] = dict()
        self.lock.acquire()
        if type(result) == str:
            result = Cache.TRANSLATE[result]
        self.L1[plugin][username][password] = {
            "timestamp": timestamp,
            "result": result,
            "output": output,
            "in_db": False,
        }
        self.diff += 1
        self.lock.release()
        if self.diff > Cache.WRITEBACK_DIFF_THRESHOLD:
            self.write_back()

    def user_exists(self, username, plugin):
        if not plugin in self.L1:
            return True
        if not username in self.L1[plugin]:
            return True
        for p in self.L1[plugin][username]:
            if self.L1[plugin][username][p]["result"] == Cache.RESULT_INEXISTANT:
                return False
        return True

    def user_exists_multiplugin(self, _username_list, _plugin_list):
        assert len(_username_list) == len(_plugin_list)
        username_list = list(_username_list)
        plugin_list = list(_plugin_list)
        r = True
        for i in range(len(username_list)):
            r &= self.user_exists(username_list[i], plugin_list[i])
        return r

    def user_success(self, username, plugin):
        if not plugin in self.L1:
            return False
        if not username in self.L1[plugin]:
            return False
        for p in self.L1[plugin][username]:
            if self.L1[plugin][username][p]["result"] == Cache.RESULT_SUCCESS:
                return True
        return False

    def user_success_multiplugin(self, _username_list, _plugin_list):
        assert len(_username_list) == len(_plugin_list)
        username_list = list(_username_list)
        plugin_list = list(_plugin_list)
        r = False
        for i in range(len(username_list)):
            r |= self.user_success(username_list[i], plugin_list[i])
        return r

    def get_last_user_timestamp(self, username, plugin):
        if not plugin in self.L1:
            return 0
        if not username in self.L1[plugin]:
            return 0
        ts = 0
        for p in self.L1[plugin][username]:
            ts = max(ts, self.L1[plugin][username][p]["timestamp"])
        return ts

    def get_last_user_timestamp_multiplugin(self, _username_list, _plugin_list):
        assert len(_username_list) == len(_plugin_list)
        username_list = list(_username_list)
        plugin_list = list(_plugin_list)
        x = 0
        for i in range(len(username_list)):
            x = max(x, self.get_last_user_timestamp(username_list[i], plugin_list[i]))
        return x

    def get_last_plugin_timestamp(self, plugin):
        if not plugin in self.L1:
            return 0
        ts = 0
        for u in self.L1[plugin]:
            for p in self.L1[plugin][u]:
                ts = max(ts, self.L1[plugin][u][p]["timestamp"])
        return ts

    def query_creds(self, username, password, plugin):
        if not plugin in self.L1:
            return None
        if not username in self.L1[plugin]:
            return None
        if not password in self.L1[plugin][username]:
            return None
        return self.L1[plugin][username][password]

    def query_creds_multiplugin(self, _username_list, password, _plugin_list):
        assert len(_username_list) == len(_plugin_list)
        username_list = list(_username_list)
        plugin_list = list(_plugin_list)
        for i in range(len(username_list)):
            x = self.query_creds(username_list[i], password, plugin_list[i])
            if x is not None:
                return x
        return None
