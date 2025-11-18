import requests

OPA_QUERY_URL = "http://localhost:8181/v1/query"

def call_consent_policy(user_id: str, input_data: dict) -> bool:
    """
    Call data.consent.may_process_or_store(user_id) in Rego,
    passing input_data as `input`.
    """

    query = f'data.consent.may_process_or_store("{user_id}")'

    payload = {
        "query": query,
        "input": input_data,
    }

    res = requests.post(OPA_QUERY_URL, json=payload)
    res.raise_for_status()

    data = res.json()
    results = data.get("result", [])

    # - results non-empty  -> expression is true
    # - results empty/missing -> expression is false
    return len(results) > 0
