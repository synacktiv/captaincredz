class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = pluginargs
    
    def validate(self):
        """
        This functions verifies if the plugin args are correctly defined
        """
        err = ""
        if not "url" in self.pluginargs:
            err = "You should include a 'url' plugin parameter"
        return "url" in self.pluginargs, err

    def testconnect(self, useragent):
        """
        This functions verifies if everything is running smoothly network-wise
        """
        # return True
        r = self.requester.get(self.pluginargs["url"] + "/check", headers={"User-Agent": useragent})
        return r.status_code == 200
    
    def test_authenticate(self, username, password, useragent):
        """
        This functions authenticates and returns data_response
        """
        data_response = {
            "result": None, # either "success", "inexistant", "potential" or "failure"
            "error": False, # if there's an error (to indicate that a retry is needed)
            "output": "Blah", # return message
            "request": None # represents the request, useful for example to print the cookies obtained
        }
        # data_response["result"] = "success"
        # return data_response
        try:
            resp = self.requester.get(f"{self.pluginargs['url']}/login", params={"username": username, "password": password, "pluginId": 1}, headers={"User-Agent": useragent})
            data_response['request'] = resp
            if resp.status_code == 200 and "Greeting" in resp.text:
                data_response['result'] = "success"
                data_response['output'] = f"[+] SUCCESS: {username}:{password}"
            elif resp.status_code == 200 and "is invalid" in resp.text:
                data_response['result'] = "inexistant"
                data_response['output'] = f"[-] User {username} does not exist"
            elif resp.status_code != 200:
                data_response['error'] = True
                data_response['output'] = "The server did not respond"
            else:
                data_response['result'] = "failure"
                data_response['output'] = f"[-] FAIL: {username}:{password}"

        except Exception as ex:
            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())

        return data_response
