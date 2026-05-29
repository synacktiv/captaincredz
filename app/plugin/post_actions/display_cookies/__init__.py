from json import dumps

def action(username, password, httpresponse, plugin, result, action_params=None):
    d = httpresponse.cookies.get_dict()
    if len(d) == 0:
        print(f"[POST-ACTION][Cookies] - \tNo cookies associated with this response")
    else:
        safe_username = username
        for c in '/.#@':
            safe_username = safe_username.replace(c, '_')
        filename = f"{safe_username}.cookies"
        with open(filename, "w+") as f:
            f.write(dumps(d))
        print(f"[POST-ACTION][Cookies] - \tYour cookies have been written to {filename}")