import sys
from bs4 import BeautifulSoup

class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = pluginargs
    
    def validate(self):
        err = None
        pak = self.pluginargs.keys()
        if not "url" in pak:
            err = "Keycloak plugin needs 'url' argument. Please add it to the config file, specifying the URL to the keycloak instance."
        if not "realm" in pak:
            err = "Keycloak plugin needs 'realm' argument. Please add it to the config file, specifying the name of the realm."
        if not "failure-string" in pak:
            err = "Keycloak plugin needs 'failure-string' argument. Please add it to the config file, specifying a string that appears when authentication fails."
        return "url" in pak and "realm" in pak and "failure-string" in pak, err

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

        try:
            realm = self.pluginargs["realm"]
            failure_string = self.pluginargs["failure-string"]

            ACCOUNT_URL = f"{self.pluginargs['url']}auth/realms/{realm}/account"

            session = self.requester.Session()

            # Emitting the first request to the target realm "account" service.
            # This should return a 302 Redirect (if not, the Keycloak installation is different and we should abort)
            r = session.get(ACCOUNT_URL, headers={"User-Agent": useragent}, allow_redirects=False)
            if r.status_code != 302:
                print("[!] Account service request did not return expected 302 - Keycloak installation may be different. Investigate if there are a lot of this.")
                raise Exception("[!] Account service request did not return expected 302 - Keycloak installation may be different. Investigate if there are a lot of this.")

            redirect_target = r.headers["Location"]

            # Emitting the second request to generated redirect URL
            # This should return a 200 OK, set 3 cookies and include the HTML form "kc-form-login"
            r = session.get(redirect_target, headers={"User-Agent": useragent})
            if r.status_code != 200:
                print("[!] Something went wrong during redirect request, which did not return expected 200. Investigate if there are a lot of this.")
                raise Exception("[!] Something went wrong during redirect request, which did not return expected 200. Investigate if there are a lot of this.")

            parser = BeautifulSoup(r.text, "html.parser")
            login_form = parser.find('form', id='kc-form-login')
            if login_form:
                action_value = login_form.get('action')
            else:
                print("[!] Could not find expected login form in redirect request response. Investigate if there are a lot of this.")
                raise Exception("[!] Could not find expected login form in redirect request response. Investigate if there are a lot of this.")

            # Emitting the third final request to actually perform the login attempt from action URL
            # Upon failure, this will return a 200 OK response containing the failure string
            payload = {"username": username, "password": password, "credentialId": ""}
            for cookie in session.cookies:
                # WARNING: MAKE SURE IT WORKS FINE TO RETRIEVE THE NEW PATH
                cookie.path = f'/{self.pluginargs["url"].split("/", 3)[3]}{cookie.path[1:]}'
                session.cookies.set_cookie(cookie)
            r = session.post(action_value, headers={"User-Agent": useragent}, data=payload)
            data_response['request'] = r

            if r.status_code != 200:
                data_response['result'] = "potential"
                data_response['output'] = f"[?] POTENTIAL - The login request returned a {r.status_code} code instead of the expected 200 which might indicate a success.: => {username}:{password}"

            elif failure_string in r.text:
                data_response['result'] = "failure"
                data_response['output'] = f"[-] FAILURE (expected failure string returned) => {username}:{password}"

            else:
                data_response['result'] = "potential"
                data_response['output'] = f"[?] POTENTIAL - The login request returned a 200 response that does not contain expected failure string => {username}:{password}"

        except Exception as ex:
            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())
            pass

        return data_response
