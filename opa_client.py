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

def call_lawful_policy(user_id: str, input_data: dict) -> bool:
    """
    Calls data.lawful.lawful_processing(user_id)
    and returns True/False properly.
    """

    query = f'x := data.lawful.lawful_processing("{user_id}")'

    payload = {
        "query": query,
        "input": input_data,
    }

    res = requests.post(OPA_QUERY_URL, json=payload)
    res.raise_for_status()

    data = res.json()
    results = data.get("result", [])

    if not results:
        return False

    # OPA returns {"result": [{"x": true/false}]}
    return bool(results[0]["x"])

def call_information_policy(user_id: str, input_data: dict) -> dict:
    """
    Calls: data.information.information(user_id)
    Returns the resulting object (dict).
    """
    query = f'x := data.information.information("{user_id}")'

    payload = {
        "query": query,
        "input": input_data,
    }

    res = requests.post(OPA_QUERY_URL, json=payload)
    res.raise_for_status()

    data = res.json()
    results = data.get("result", [])
    if not results:
        return {}

   
    return results[0].get("x", {})

def call_access_policy(user_id: str, input_data: dict) -> dict:
    """
    Calls: data.access.access_response(user_id)
    Returns the resulting object (dict).
    """
    query = f'x := data.access.access_response("{user_id}")'
    payload = {"query": query, "input": input_data}

    res = requests.post(OPA_QUERY_URL, json=payload)
    res.raise_for_status()

    data = res.json()
    results = data.get("result", [])
    if not results:
        return {}

    return results[0].get("x", {})

def call_rectification_policy(user_id: str, input_data: dict) -> dict:
    query = f'x := data.rectification.rectification_response("{user_id}")'
    payload = {"query": query, "input": input_data}

    res = requests.post(OPA_QUERY_URL, json=payload)

    # 👇 show OPA's error message instead of just "400 Bad Request"
    if res.status_code != 200:
        print("OPA status:", res.status_code)
        print("OPA response body:", res.text)
        print("OPA query was:", query)
        raise RuntimeError("OPA query failed")

    data = res.json()
    results = data.get("result", [])
    if not results:
        return {}
    return results[0].get("x", {})
