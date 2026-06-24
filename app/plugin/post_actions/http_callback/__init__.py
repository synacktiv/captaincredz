import requests

methods = {"get": requests.get, "post": requests.post, "put": requests.put, "delete": requests.delete}

def action(username, password, httpresponse, plugin, result, action_params=None):
    proxy = action_params.get("proxy", None)
    url = action_params.get("url", None)
    method = action_params.get("method", "get")
    params = action_params.get("params", dict())

    if url is None:
        return None
    if not method in methods:
        return None
    if type(params) != dict:
        return None
    if type(proxy) == str:
        proxy = {"http": proxy, "https":proxy}
    
    resp = methods[method](url, params=params, proxies=proxy)
    return resp.status_code


"""
    "post_actions": {
        "http_callback": {
            "triggers": ["success"],
            "params": {
                "proxy": "http://127.0.0.1:3128",
                "url": "http://notification-app.com/my-endpoint",
                "params": {
                    "api_key": "MYAPIKEYISSUPERSECRET"
                }
            }
        }
    }
"""