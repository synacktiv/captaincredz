import threading
import random
import time
from queue import deque
import datetime
import csv


class User:
    def __init__(self):
        self.usernames = []
        self.passwords = deque([])
        self.inflight = []
        self.trimmed = False
        self.ready = True

    def __str__(self):
        ret = "Usernames: " + str(self.usernames) + "\n"
        ret += "\tPasswords: " + str(self.passwords) + "\n"
        ret += "\tInflight: " + str(self.inflight) + "\n"
        ret += "\tTrimmed: " + str(self.trimmed) + "\n"
        ret += "\tReady: " + str(self.ready) + "\n"
        ret += "\tID: " + str(id(self)) + "\n"
        return ret

    def __repr__(self):
        return self.__str__()


class CredSet:
    def __init__(self):
        self.users = []  # [User]

    def add_user(self, usernames=None, passwords=None):
        if usernames is None:
            usernames = []
        if passwords is None:
            passwords = []

        # Merge user if it exists (like upsert)
        exists = False
        u = None
        for _u in self.users:
            if all([a == b for a, b in zip(_u.usernames, usernames)]):
                u = _u
                exists = True
                break

        if exists:
            u.passwords.extend(passwords)
        else:
            u = User()
            u.usernames = usernames
            u.passwords = deque(passwords)
            u.inflight = []
            u.trimmed = False
            u.ready = True
            self.users.append(u)

    def add_password(self, password):
        for u in self.users:
            u.passwords.append(password)

    def add_passwords(self, passwords):
        for u in self.users:
            u.passwords.extend(passwords)

    def get_next_user(self):
        maxLen = -1
        maxI = -1
        for i in range(len(self.users)):
            if (
                self.users[i].ready
                and not self.users[i].trimmed
                and len(self.users[i].passwords) > maxLen
            ):
                maxLen = len(self.users[i].passwords)
                maxI = i
        if maxLen > 0:
            p = self.users[maxI].passwords.popleft()
            self.users[maxI].inflight.append(p)
            self.users[maxI].ready = False
            return self.users[maxI].usernames, p
        else:
            return None, None

    def garbage_collect(self):
        self.users = [u for u in self.users if not u.trimmed]

    def trim_user(self, username, plugin_id):
        for u in self.users:
            if u.usernames[plugin_id] == username:
                u.trimmed = True
                break

    @property
    def finished(self):
        return all([u.trimmed for u in self.users])

    @property
    def length(self):
        return sum(
            [len(u.passwords) + len(u.inflight) for u in self.users if not u.trimmed]
        )


class Sleeper:
    SLEEP_INTERVAL = 2
    WW_SLEEP_INTERVAL = 60

    def __init__(self, delays, start_date):
        self._delays = delays
        self._cancelled = False
        self._start_date = start_date

    def ww_calc_factor(self):
        if self._delays["ww"] is None:
            return 1
        now = datetime.datetime.now(
            datetime.timezone(
                datetime.timedelta(hours=self._delays["ww"]["utc_offset"])
            )
        )
        day_factor = Sleeper.clamp(
            self._delays["ww"]["days_factor"][now.strftime("%A")[:3].lower()], 0, 1
        )
        hour_factor = Sleeper.clamp(
            self._delays["ww"]["hours_factor"][str(now.hour)], 0, 1
        )
        rampup_factor = (datetime.datetime.now() - self._start_date).total_seconds() / (
            24 * 60 * 60
        )
        rampup_factor = rampup_factor * (self._delays["ww"]["daily_speedup"] - 1) + 1
        rampup_factor = rampup_factor * self._delays["ww"]["initial_speed"]
        rampup_factor = min(rampup_factor, 1)
        total_factor = day_factor * hour_factor * rampup_factor
        # Should never be useful, but there in any case
        total_factor = Sleeper.clamp(total_factor, 0, 1)
        return total_factor

    def cancellable_sleep(self, sec):
        delay_total = sec
        delay_turns = round(delay_total // Sleeper.SLEEP_INTERVAL)
        for _ in range(delay_turns):
            if self._cancelled:
                return False
            time.sleep(Sleeper.SLEEP_INTERVAL)
        if self._cancelled:
            return False
        time.sleep(delay_total % Sleeper.SLEEP_INTERVAL)
        return True

    def weighted_cancellable_sleep(self, t):
        to_sleep_time = t
        slept_time = 0
        while slept_time < to_sleep_time and not self._cancelled:
            f = self.ww_calc_factor()
            s = Sleeper.WW_SLEEP_INTERVAL
            if f > 0.01:
                s = min(s, (to_sleep_time - slept_time) / f)
            self.cancellable_sleep(s)
            slept_time += s * f
        return not self._cancelled

    def user_sleep(self, custom_delay=None):
        if self._cancelled:
            return
        d = self._delays["user"]
        if custom_delay is not None:
            d = custom_delay
        sleep_time = d + random.random() * self._delays["jitter"]
        self.weighted_cancellable_sleep(sleep_time)

    def request_sleep(self, t=None):
        if self._cancelled:
            return
        if t is None:
            t = self._delays["req"] + random.random() * self._delays["jitter"]
        self.weighted_cancellable_sleep(t)

    def chunk_sleep(self):
        if self._cancelled:
            return
        sleep_time = (
            self._delays["chunk_delay"] + random.random() * self._delays["jitter"]
        )
        self.weighted_cancellable_sleep(sleep_time)

    @staticmethod
    def clamp(x, m, M):
        return max(m, min(M, x))


class Pool:
    CSV_DELIMITER = ";"
    USERPASS_DELIMITER = ":"

    def __init__(
        self, userfile, passwordfile, userpassfile, delays, cache, workers, logger
    ):
        self.cache = cache
        self.logger = logger
        self.workers = workers
        self.cancelled = False
        self.get_creds_lock = threading.Lock()
        self.chunk_count = 0
        self.attempts_count = 0

        self.credset = CredSet()
        self.sleeper = Sleeper(delays, datetime.datetime.now())

        # I'm not smart here so that this is trivially correct and not overengineered
        # It can be improved by filtering with cache when creating, but it implies more complex code

        # Step 1 : Create everything
        if userfile is not None:
            with open(userfile, "r") as f:
                for username_list in csv.reader(f, delimiter=Pool.CSV_DELIMITER):
                    self.credset.add_user(usernames=username_list)
        if userpassfile is not None:
            with open(userpassfile, "r") as f:
                x = [
                    up.rstrip("\n").split(Pool.USERPASS_DELIMITER, 1)
                    for up in f.readlines()
                ]
                for ulp in x:
                    assert len(ulp) == 2
                    ul, p = ulp
                    self.credset.add_user(
                        usernames=ul.split(Pool.CSV_DELIMITER), passwords=[p]
                    )
        if passwordfile is not None:
            with open(passwordfile, "r") as f:
                self.credset.add_passwords(
                    [
                        p.rstrip("\r\t\n")
                        for p in f.readlines()
                        if len(p.rstrip("\r\t\n")) > 0
                    ]
                )

        # Step 2 : Remove the cache hits from the creds set
        # 2.1 : remove inexistant and successful users
        plugins = [w.plugin for w in self.workers]
        for user in self.credset.users:
            usernames = user.usernames
            exists = self.cache.user_exists_multiplugin(usernames, plugins)
            already_success = self.cache.user_success_multiplugin(usernames, plugins)
            if not (exists and not already_success):
                user.trimmed = True
        # 2.2 : remove already tried passwords for the rest of users
        for user in self.credset.users:
            usernames = user.usernames
            filtered_passwords = []
            for p in user.passwords:
                cache_result = self.cache.query_creds_multiplugin(usernames, p, plugins)
                if cache_result is None:
                    filtered_passwords.append(p)
            user.passwords = deque(filtered_passwords)
        self.credset.garbage_collect()

        # Step 3 : Set the ready state with the last timestamp for each user
        for user in self.credset.users:
            usernames = user.usernames
            last_timestamp = self.cache.get_last_user_timestamp_multiplugin(
                usernames, plugins
            )
            ts_now = datetime.datetime.now().timestamp()
            last_sprayed_delay = ts_now - last_timestamp
            if last_sprayed_delay < self.sleeper._delays["user"]:
                user.ready = False
                threading.Thread(
                    target=self.user_delay_thread,
                    args=(user, self.sleeper._delays["user"] - last_sprayed_delay),
                ).start()

    def apply_delays(self, user):
        if self.cancelled:
            return
        thread_request = threading.Thread(target=self.request_delay_thread)
        thread_user = threading.Thread(target=self.user_delay_thread, args=(user,))
        thread_request.start()
        thread_user.start()

    def user_delay_thread(self, user, custom_delay=None):
        self.sleeper.user_sleep(custom_delay)
        try:
            user.ready = True
        except:
            # user was probably trimmed during sleep or something
            pass

    def request_delay_thread(self, t=None):
        self.chunk_count += 1
        if (
            self.sleeper._delays["chunk_size"] > 0
            and self.chunk_count >= self.sleeper._delays["chunk_size"]
        ):
            self.chunk_count = 0
            self.sleeper.chunk_sleep()
        self.sleeper.request_sleep(t)

        try:
            self.get_creds_lock.release()
        except Exception as ex:
            if "unlocked lock" in str(ex):
                pass  # OK
            else:
                pass  # Weird

    def trim_user(self, username, worker_id):
        self.logger.debug(f"Trimming {username}")
        self.credset.trim_user(username, worker_id)

    def get_creds(self, filtered_workers):
        if self.cancelled:
            return None, None
        self.get_creds_lock.acquire()

        # Start off by picking an available worker
        try:
            worker_id = random.choices(
                range(len(filtered_workers)), [w.weight for w in filtered_workers]
            )[0]
        except:
            self.logger.debug(
                f"Workers are all finished, will not return any more credz..."
            )
            return None, None

        # Then pick a username/password
        usernames = None
        password = None
        while usernames is None and not self.cancelled:
            usernames, password = self.credset.get_next_user()
            if usernames is None:
                self.credset.garbage_collect()
                time.sleep(Sleeper.SLEEP_INTERVAL)
            if self.credset.length == 0:
                self.stop()
        if usernames is None:
            try:
                self.get_creds_lock.release()
            except Exception as ex:
                if "unlocked lock" in str(ex):
                    pass  # OK
                else:
                    print("BBBB")
                    pass  # Weird
            return None, None

        username = usernames[filtered_workers[worker_id].id]

        self.attempts_count += 1
        return {"username": username, "password": password}, worker_id

    def signal_tried(self, username, password, plugin_id, error=False):
        if error:
            self.attempts_count -= 1
        user = None
        for u in self.credset.users:
            if u.usernames[plugin_id] == username:
                user = u
                break
        if user is None:
            if self.get_total_size() == 0:
                self.stop()
            return

        try:
            user.inflight.remove(password)
        except:
            pass

        self.apply_delays(user)
        if error:
            user.passwords.appendleft(password)
        else:
            if self.get_total_size() == 0:
                self.stop()

    def stop(self):
        self.cancelled = True
        self.sleeper._cancelled = True

    def get_total_size(self):
        return self.credset.length
