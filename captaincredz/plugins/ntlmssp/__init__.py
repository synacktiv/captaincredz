"""
author: lou
quick & dirty POC of an NTLM authentication plugin
"""

import spnego
import os
import base64

class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = pluginargs

    def validate(self):
        """
        This functions verifies if the plugin args are correctly defined
        """
        err = "You must provide an url and protocol (either 'ntlm' or 'negotiate')"
        if any(i not in self.pluginargs for i in ["url", "protocol"]):
            return False, err
        if not any(i in self.pluginargs["protocol"] for i in ["ntlm", "negotiate"]):
            return False, err
        return True, err

    def testconnect(self, useragent):
        """
        This functions verifies if everything is good network-wise
        """
        # return True
        r = self.requester.get(self.pluginargs["url"], headers={"User-Agent": useragent, "Authorization": "NTLM"})
        is_401 = r.status_code == 401
        supports_authentication = any([i.lower() in r.headers.get("WWW-Authenticate").lower() for i in ["NTLM", "Negotiate"]])
        return is_401 and supports_authentication

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
            data = username.split("@")
            if len(data) == 2:
                username, domain = data
                workstation = "DESKTOP-5EE1C34"
            elif len(data) == 3:
                username, domain, workstation = data
            else:
                raise Exception("Users should be in the username@domain[@workstation] format")

            # ugly but works
            os.environ["NETBIOS_COMPUTER_NAME"] = workstation

            ntlm_client = spnego.client(username, password, domain, protocol=self.pluginargs["protocol"])
            sess = self.requester.session()
            sess.headers.update({"User-Agent": useragent})

            ntlm_negotiate_message = ntlm_client.step()
            beautiful_protocol = "NTLM"
            if self.pluginargs["protocol"].lower() == "negotiate":
                beautiful_protocol = "Negotiate"

            resp = sess.get(self.pluginargs["url"], headers={"Authorization": f"{beautiful_protocol} {base64.b64encode(ntlm_negotiate_message).decode()}"})

            ntlm_authenticate_message = ntlm_client.step(base64.b64decode(resp.headers.get("WWW-Authenticate").split(" ")[1]))
            resp = sess.get(self.pluginargs["url"], headers={"Authorization": f"{beautiful_protocol} {base64.b64encode(ntlm_authenticate_message).decode()}"})

            data_response['request'] = resp
            if resp.status_code != 401:
                data_response['result'] = "success"
                data_response['output'] = f"[+] SUCCESS: {domain}\\{username}:{password}"
            elif resp.status_code == 401:
                data_response['result'] = "failure"
                data_response['output'] = f"[-] FAIL: {domain}\\{username}:{password}"

        except Exception as ex:
            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())

        return data_response
