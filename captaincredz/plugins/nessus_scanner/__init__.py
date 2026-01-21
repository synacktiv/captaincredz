class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = pluginargs

    def validate(self):
        """
        This functions verifies if the plugin args are correctly defined
        """
        err = "You must provide an url"
        if "url" not in self.pluginargs:
            return False, err
        return True, err

    def testconnect(self, useragent):
        """
        This functions verifies if everything is good network-wise
        """
        url = f'{self.pluginargs["url"].rstrip("/")}/server/status'
        r = self.requester.get(url, headers={"User-Agent": useragent})
        return r.status_code == 200

    def test_authenticate(self, username, password, useragent):
        """
        This functions authenticates
        """
        data_response = {
            "result": None, # either "success", "inexistant", "potential" or "failure"
            "error": False, # if there's an error (to indicate that a retry is needed)
            "output": "Blah", # return message
            "request": None # represents the request, useful for example to print the cookies obtained
        }

        try:
            url = f'{self.pluginargs["url"].rstrip("/")}/session'
            
            sess = self.requester.session()
            sess.headers.update({"User-Agent": useragent})

            data = {"username": username, "password": password}
            resp = sess.post(url, json=data, allow_redirects=False)

            data_response['request'] = resp
            if resp.status_code == 401:
                data_response['result'] = "failure"
                data_response['output'] = f"[-] FAIL: {username}:{password}"
            else:
                data_response['result'] = "potential"
                data_response['output'] = f"[+] POTENTIAL: {username}:{password}"

        except Exception as ex:
            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())

        return data_response
