import random
import requests

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)


class Requester:
    def __init__(self, useragentfile=None, proxy=None, headers=None, req_timeout=60):
        self.useragents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ]  # By default: Win10 with Chrome 130
        if useragentfile is not None:
            with open(useragentfile, "r") as f:
                self.useragents = [ua.rstrip() for ua in f.readlines()]
        self.proxy = {"http": proxy, "https": proxy}
        self.headers = headers
        self.request_timeout = req_timeout

    def get_random_ua(self):
        return random.choice(self.useragents)

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
        if not "headers" in dico or not "user-agent" in [
            x.lower() for x in list(dico["headers"])
        ]:
            # TODO add warning ?
            if "headers" in dico:
                dico["headers"]["User-Agent"] = self.get_random_ua()
            else:
                dico["headers"] = {"User-Agent": self.get_random_ua()}
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
