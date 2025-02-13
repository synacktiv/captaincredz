from json import dumps

def action(username, password, timestamp, httpresponse, plugin, result, logger, action_params=None):
    d = httpresponse.cookies.get_dict()
    if len(d) == 0:
        logger.info(f"[POST-ACTION][Cookies] - \tNo cookies associated with this response")
    else:
        safe_username = username
        for c in '/.#@':
            safe_username = safe_username.replace(c, '_')
        filename = f"{safe_username}_{int(timestamp)}.cookies"
        with open(filename, "w+") as f:
            f.write(dumps(d))
        logger.info(f"[POST-ACTION][Cookies] - \tYour cookies have been written to {filename}")