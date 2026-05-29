import requests

"""
{
  "post_actions: {
    "aws_sms_notify": {
      "triggers": ["success"],
      "params": {
        "lambda_id": "abdef",
        "param_name": "blabla",
        "proxy": null
      }
    }
  }
}
"""

def action(username, password, request, plugin, result, action_params=None):
    if type(action_params) is not dict or not "lambda_id" in action_params or not "param_name" in action_params:
        return False
    url = f"https://{action_params.get("lambda_id")}.lambda-url.eu-west-3.on.aws/"
    requests.get(url, params={action_params.get("param_name"): 'Hit on spray'}, proxies={'http': action_params.get("proxy"), 'https': action_params.get("proxy")})
