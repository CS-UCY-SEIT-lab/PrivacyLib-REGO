import requests

OPA_QUERY_URL = "http://localhost:8181/v1/query"

def call_consent_policy(user_id: str, input_data: dict) -> bool:
    query = f'x := data.consent.may_process_or_store("{user_id}")'
    payload = {"query": query, "input": input_data}

    res = requests.post(OPA_QUERY_URL, json=payload)
    res.raise_for_status()

    data = res.json()
    results = data.get("result", [])
    if not results:
        return False

    return bool(results[0]["x"])
