from typing import Any, Dict, Optional
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

# Erasure integration : (4) Notify data subject + (5) Notify storage period

def _opa_query(query: str, input_data: Dict[str, Any]) -> Optional[Any]:
    """
    Executes an OPA query and returns the value bound to 'x', or None.
    Uses the /v1/query endpoint (your current pattern).
    """
    payload = {"query": query, "input": input_data}
    res = requests.post(OPA_QUERY_URL, json=payload)

    if res.status_code != 200:
        print("OPA status:", res.status_code)
        print("OPA response body:", res.text)
        print("OPA query was:", query)
        raise RuntimeError("OPA query failed")

    data = res.json()
    results = data.get("result", [])
    if not results:
        return None

    return results[0].get("x")


def call_erasure_policy(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
      {
        "decision": "accept"|"reject",
        "justification": [...],
        "actions": {...}
      }
    """
    decision = _opa_query("x := data.privacy.erasure.decision", input_data)
    justification = _opa_query("x := data.privacy.erasure.justification", input_data)
    actions = _opa_query("x := data.privacy.erasure.actions", input_data)

    # Normalize missing values
    if decision is None:
        decision = "reject"
    if justification is None:
        justification = []
    if actions is None:
        actions = {}

    return {
        "decision": decision,
        "justification": justification,
        "actions": actions,
    }

def notify_data_subject(notification: Dict[str, Any], dpo: Dict[str, Any], controller: Dict[str, Any]) -> None:
    """
    Placeholder: implement email, webhook, queue publish, etc.
    This prints a message so you can see it working.
    """
    # You can plug in SMTP, SendGrid, etc. here
    print("\n--- NOTIFY DATA SUBJECT ---")
    print("Controller:", controller.get("name"), controller.get("email"))
    print("DPO:", dpo.get("name"), dpo.get("email"))
    print("Decision:", notification.get("decision"))
    print("Request ID:", notification.get("request_id"))
    if "justification" in notification:
        print("Justification:", notification.get("justification"))
    if "details" in notification:
        print("Details:", notification.get("details"))
    print("--- END NOTIFY ---\n")


def notify_storage_period_and_criteria(storage_info: Dict[str, Any]) -> None:
    """
    Step (5): notify data subject of period and criteria used to store their data.
    In many systems this is part of the same email/response payload; here it's separate.
    """
    print("\n--- STORAGE PERIOD & CRITERIA ---")
    print("Retention period:", storage_info.get("period"))
    print("Retention criteria:", storage_info.get("criteria"))
    print("--- END STORAGE INFO ---\n")


def process_erasure_request(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    main function that:
      - Calls OPA erasure policy
      - Execute (4) notify subject w/ justification if rejected (or acceptance details if accepted)
      - Execute (5) notify storage period & criteria
      - Returns policy output so caller can apply delete/log/third-party notifications, etc.
    """
    result = call_erasure_policy(input_data)
    actions = result.get("actions", {}) or {}

    # (4) notify data subject
    notify_payload = actions.get("notify_data_subject")
    if notify_payload:
        notify_data_subject(
            notification=notify_payload,
            dpo=input_data.get("dpo", {}),
            controller=input_data.get("controller", {})
        )

    # (5) notify period and criteria used to store data
    storage_payload = actions.get("notify_storage_period_and_criteria")
    if storage_payload:
        notify_storage_period_and_criteria(storage_payload)


    return result