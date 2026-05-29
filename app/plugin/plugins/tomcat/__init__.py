import base64

class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = pluginargs

    def validate(self):
        """
        This functions verifies if the plugin args are correctly defined
        """

        if "url" not in self.pluginargs:
            return False, "You must provide an URL with an running Apache Tomcat instance"
        else:
            if self.pluginargs.get("method") == None:
                method = "GET"
            else:
                method = self.pluginargs["method"]
            self.pluginargs["method"] = method # Save the method

            if method not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "CONNECT", "TRACE"]:
                return False, f"Unknown HTTP method '{method}' provided"
            else:
                return True, None

    def testconnect(self, useragent):
        """
        This functions verifies if everything is good network-wise
        """

        method = self.pluginargs["method"]
        r = self.requester.request(method, self.pluginargs["url"], headers = {"User-Agent": useragent})
        is_401 = r.status_code == 401
        supports_authentication = "Basic" in r.headers.get("WWW-Authenticate")

        return is_401 and supports_authentication

    def test_authenticate(self, username, password, useragent):
        """
        This functions authenticates
        """

        data_response = {
            "result": None, # either "success", "inexistant", "potential" or "failure"
            "error": False, # if there's an error (to indicate that a retry is needed)
            "output": None, # return message
            "request": None # represents the request, useful for example to print the cookies obtained
        }

        try:

            method = self.pluginargs["method"]
            authorization = base64.b64encode(username.encode() + b':' + password.encode()).decode()
            r = self.requester.request(method, self.pluginargs["url"], headers = {"User-Agent": useragent, "Authorization": f"Basic {authorization}"}, allow_redirects = False)
            data_response['request'] = r

            if r.status_code == 401: # Wrong credentials

                data_response['result'] = 'failure'
                data_response['output'] = 'Invalid credentials'
            
            else: # Consider other error codes as valid credentials

                data_response['result'] = 'success'
                data_response['output'] = f"Valid credentials found with returned status code {r.status_code}"

        except Exception as ex:

            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())

        return data_response
