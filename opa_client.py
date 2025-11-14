import requests

OPA_URL = "http://localhost:8181/v1/data"

def evaluate(path: str, input_data: dict):
    """
    path: e.g. "consent/may_process_or_store"
    input_data: dict that becomes `input` in Rego
    """
    url = f"{OPA_URL}/{path}"
    payload = {"input": input_data}

    res = requests.post(url, json=payload)
    res.raise_for_status()
    return res.json().get("result")
