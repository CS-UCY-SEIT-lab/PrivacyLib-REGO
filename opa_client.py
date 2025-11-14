import requests

OPA_QUERY_URL = "http://localhost:8181/v1/query"

def call_consent_policy(user_id: str, input_data: dict) -> bool:
    """
    Call data.consent.may_process_or_store(user_id) in Rego,
    passing input_data as `input`.
    """

    # Build the Rego query string, e.g.:
    # data.consent.may_process_or_store("1")
    query = f'data.consent.may_process_or_store("{user_id}")'

    payload = {
        "query": query,
        "input": input_data,
    }

    res = requests.post(OPA_QUERY_URL, json=payload)
    # You can print res.text for debugging if something goes wrong
    res.raise_for_status()

    data = res.json()
    # /v1/query response looks like:
    # {
    #   "result": [
    #     {
    #       "expressions": [
    #         { "value": true, ... }
    #       ]
    #     }
    #   ]
    # }
    results = data.get("result", [])
    if not results:
        return False

    exprs = results[0].get("expressions", [])
    if not exprs:
        return False

    return bool(exprs[0].get("value"))
