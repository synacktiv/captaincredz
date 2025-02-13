class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = pluginargs
        if self.pluginargs is None:
            self.pluginargs = dict()
    
    def validate(self):
        #
        # Plugin Args
        #
        # --url https://adfs.domain.com   ->  ADFS target
        #
        err = None
        if not "url" in self.pluginargs.keys():
            err = "ADFS plugin needs 'url' argument. Please add it to the configuration, specifying the URL to the ADFS instance (without /adfs/ls)."
        return "url" in self.pluginargs.keys(), err

    def testconnect(self, useragent):
        resp = self.requester.get(self.pluginargs["url"], headers={'User-Agent': useragent})

        return resp.status_code != 504

    def test_authenticate(self, username, password, useragent):
        data_response = {
            'result' : None,    # Can be "success", "failure", "potential" or "inexistant"
            'error' : False,
            'output' : "",
            'request': None
        }

        post_data = {
            'UserName' : username,
            'Password' : password,
            'AuthMethod' : 'FormsAuthentication'
        }

        # ?client-request-id=&wa=wsignin1.0&wtrealm=urn:federation:MicrosoftOnline&wctx=cbcxt=&username={}&mkt=&lc=
        params_data =  {
            'client-request-id' : '',
            'wa' : 'wsignin1.0',
            'wtrealm' : 'urn:federation:MicrosoftOnline',
            'wctx' : '',
            'cbcxt' : '',
            'username' : username,
            'mkt' : '',
            'lc' : '',
            'pullStatus' : 0
        }

        headers = {
            'User-Agent': useragent,
            'Content-Type' : 'application/x-www-form-urlencoded',
            'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9, image/webp,*/*;q=0.8'
        }

        try:

            resp = self.requester.post(f"{self.pluginargs['url']}/adfs/ls/", headers=headers, params=params_data, data=post_data, allow_redirects=False)
            data_response['request'] = resp
            if resp.status_code == 302:
                data_response['result'] = "success"
                data_response['output'] = f"[+] SUCCESS: => {username}:{password}"

            else:  # fail
                data_response['result'] = "failure"
                data_response['output'] = f"[-] FAILURE: {resp.status_code} => {username}:{password}"

        except Exception as ex:
            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())
            pass

        return data_response
