from typing import Any, Dict, Optional
import requests
import json,os
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

def process_restriction_request(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single entry point for Right to Restriction of Processing.
    - Calls OPA
    - Presents purposes
    - Notifies user
    - Returns decision + actions
    """

    payload = {
        "query": "x := data.restriction",
        "input": input_data
    }

    res = requests.post(OPA_QUERY_URL, json=payload)

    if res.status_code != 200:
        print("OPA status:", res.status_code)
        print("OPA response body:", res.text)
        raise RuntimeError("OPA query failed")

    data = res.json()
    results = data.get("result", [])
    if not results:
        return {}

    result = results[0]["x"]

    decision = result.get("decision")
    actions = result.get("actions", {})
    justification = result.get("justification", [])

    # (1) Present purposes
    purposes = actions.get("present_purposes", [])
    if purposes:
        print("\n--- PRESENT PURPOSES TO USER ---")
        for p in purposes:
            print(f"{p['field']} -> {p['purpose']}")
        print("--- END PURPOSES ---\n")

    # (4) Notify user
    notify = actions.get("notify_user")
    if notify:
        print("\n--- NOTIFY USER ---")
        print("Decision:", notify.get("decision"))
        print("Request ID:", notify.get("request_id"))
        if "message" in notify:
            print("Message:", notify.get("message"))
        if "justification" in notify:
            print("Justification:", notify.get("justification"))
        print("--- END NOTIFY ---\n")

    # Enforce restriction
    stop = actions.get("stop_processing")
    if stop:
        print("\n--- STOP PROCESSING ---")
        print(stop)
        print("--- END STOP ---\n")

    # Audit log
    audit = actions.get("log_audit")
    if audit:
        print("\n--- AUDIT EVENT ---")
        print(audit)
        print("--- END AUDIT ---\n")

    return {
        "decision": decision,
        "justification": justification,
        "actions": actions
    }

def call_portability_policy(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls:
      - data.portability.decision
      - data.portability.justification
      - data.portability.actions
    """
    decision = _opa_query("x := data.portability.decision", input_data)
    justification = _opa_query("x := data.portability.justification", input_data)
    actions = _opa_query("x := data.portability.actions", input_data)

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


def process_portability_request(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Application handler for Right to Data Portability.

    Responsibilities:
      - Call OPA portability policy
      - Write machine-readable files (JSON + CSV)
      - Notify user that files are available
      - Log audit event
    """
    result = call_portability_policy(input_data)
    actions = result.get("actions", {}) or {}

    # Write machine-readable files
    downloads = actions.get("downloads", [])
    if downloads:
        os.makedirs("outputs", exist_ok=True)

        for d in downloads:
            filename = os.path.join("outputs", d["filename"])
            content = d.get("content")

            with open(filename, "w", encoding="utf-8") as f:
                if isinstance(content, dict):
                    json.dump(content, f, indent=2)
                else:
                    f.write(content)

            print(f"[+] Machine-readable file created: {filename}")

        print("\n--- NOTIFY USER ---")
        print("Your personal data is ready in machine-readable format:")
        for d in downloads:
            print("-", d["filename"])
        print("--- END NOTIFY ---\n")

    # Audit log
    audit = actions.get("log_audit")
    if audit:
        print("\n--- AUDIT EVENT ---")
        print(audit)
        print("--- END AUDIT ---\n")

    return result

def call_objection_policy(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls:
      - data.objection.decision
      - data.objection.justification
      - data.objection.actions

    Returns:
      {
        "decision": "accept"|"reject",
        "justification": [...],
        "actions": {...}
      }
    """
    decision = _opa_query("x := data.objection.decision", input_data)
    justification = _opa_query("x := data.objection.justification", input_data)
    actions = _opa_query("x := data.objection.actions", input_data)

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


def process_objection_request(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Application handler for Right to Object (GDPR Art. 21).

    Responsibilities:
      - Call OPA objection policy
      - Present processing context (purpose + legal basis) to user
      - Print notify_user payload (includes DPA complaint info if rejected)
      - Print stop_processing action if accepted
      - Print audit event for storage in your system
    """
    result = call_objection_policy(input_data)
    actions = result.get("actions", {}) or {}

    # (2) Present purpose + legal basis of processing for specified data
    ctx = actions.get("present_processing_context", [])
    if ctx:
        print("\n--- PROCESSING CONTEXT (PURPOSE + LEGAL BASIS) ---")
        for item in ctx:
            print(
                f"Field: {item.get('field')} | "
                f"Purpose: {item.get('purpose')} | "
                f"Legal basis: {item.get('legal_basis')}"
            )
        print("--- END CONTEXT ---\n")

    # Notify user (accept/reject + justification + DPA complaint notice if rejected)
    notify = actions.get("notify_user")
    if notify:
        print("\n--- NOTIFY USER (OBJECTION) ---")
        print("Decision:", notify.get("decision"))
        print("Request ID:", notify.get("request_id"))
        if "message" in notify:
            print("Message:", notify.get("message"))
        if "justification" in notify:
            print("Justification:", notify.get("justification"))
        if "complaint" in notify:
            complaint = notify.get("complaint") or {}
            print("Complaint info:", complaint.get("message"))
        print("--- END NOTIFY ---\n")

    # Stop processing action (if accepted)
    stop = actions.get("stop_processing")
    if stop:
        print("\n--- STOP PROCESSING ACTION (ENFORCE IN APP) ---")
        print(stop)
        print("--- END STOP ---\n")

    # Audit event (store in DB/log)
    audit = actions.get("log_audit")
    if audit:
        print("\n--- AUDIT EVENT (STORE FOR AUDITING) ---")
        print(audit)
        print("--- END AUDIT ---\n")

    return result

def call_breach_policy(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls:
      - data.breach.decision
      - data.breach.justification
      - data.breach.actions
    """
    decision = _opa_query("x := data.breach.decision", input_data)
    justification = _opa_query("x := data.breach.justification", input_data)
    actions = _opa_query("x := data.breach.actions", input_data)

    if decision is None:
        decision = "no_notify"
    if justification is None:
        justification = []
    if actions is None:
        actions = {}

    return {
        "decision": decision,
        "justification": justification,
        "actions": actions,
    }


def process_breach_assessment(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Application handler:
      - Calls OPA breach policy
      - If notify_users, prints composed message and writes a notification "outbox" file
      - Always prints audit event (store it in real system)
    """
    result = call_breach_policy(input_data)
    actions = result.get("actions", {}) or {}

    print("\n==========")
    print("DATA BREACH ASSESSMENT")
    print("==========")
    print("Decision:", result.get("decision"))

    # If policy says notify users
    notify = actions.get("notify_users")
    compose = actions.get("compose_message")
    if notify:
        print("\n--- COMPOSED MESSAGE (PLAIN TEXT) ---")
        if compose and compose.get("plain_text"):
            print(compose["plain_text"])
        else:
            print(notify.get("message", ""))
        print("--- END MESSAGE ---\n")

        print("--- USERS TO NOTIFY ---")
        print(notify.get("users", []))
        print("--- END USERS ---\n")

        # Write to outputs as an "outbox" record (no real sending)
        os.makedirs("outputs", exist_ok=True)
        out_path = os.path.join("outputs", f"breach_outbox_{notify.get('incident_id','unknown')}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(notify, f, indent=2)
        print(f"[+] Wrote notification outbox file: {out_path}")

    # Always log audit event (store in DB/log in real systems)
    audit = actions.get("log_audit")
    if audit:
        print("\n--- AUDIT EVENT ---")
        print(audit)
        print("--- END AUDIT ---\n")

    # If not notifying, show justification
    just = result.get("justification", [])
    if result.get("decision") != "notify_users" and just:
        print("\n--- JUSTIFICATION ---")
        for j in just:
            print("-", j)
        print("--- END JUSTIFICATION ---\n")

    return result

def call_complaint_policy(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls:
      - data.complaint.decision
      - data.complaint.justification
      - data.complaint.actions
    """
    decision = _opa_query("x := data.complaint.decision", input_data)
    justification = _opa_query("x := data.complaint.justification", input_data)
    actions = _opa_query("x := data.complaint.actions", input_data)

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


def process_complaint_request(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    App handler for Art. 77 complaint workflow:
      - Calls OPA complaint policy
      - Displays authorities list (for UI)
      - Logs audit event (prints it; you store it in DB)
      - "Forwards" complaint by writing a forward payload to outputs/ (no real sending)
      - Notifies user (prints)
    """
    result = call_complaint_policy(input_data)
    actions = result.get("actions", {}) or {}

    print("\n==========")
    print("ART. 77 - COMPLAINT WORKFLOW")
    print("==========")
    print("Decision:", result.get("decision"))

    # (4) Present list of supervisory authorities (UI)
    authorities = actions.get("authorities", [])
    if authorities:
        print("\n--- SUPERVISORY AUTHORITIES ---")
        for a in authorities:
            print(f"- {a.get('id')} | {a.get('name')} | {a.get('country')} | {a.get('channel')} -> {a.get('endpoint')}")
        print("--- END AUTHORITIES ---\n")

    # (5) Audit log (store in DB in real systems)
    audit = actions.get("log_audit")
    if audit:
        print("\n--- AUDIT EVENT ---")
        print(audit)
        print("--- END AUDIT ---\n")

    # (6) Forward complaint (no simulation: just produce a forward payload file)
    forward = actions.get("forward")
    if forward and isinstance(forward, dict) and forward:
        os.makedirs("outputs", exist_ok=True)
        authority = forward.get("authority", {})
        authority_id = authority.get("id", "unknown")
        request_id = (input_data.get("request", {}).get("complaint", {}) or {}).get("request_id", "unknown")

        out_path = os.path.join("outputs", f"complaint_forward_{request_id}_{authority_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(forward, f, indent=2)

        print(f"[+] Forward payload written: {out_path}")
        print("    (Your real system would send this to the authority endpoint.)")

    # (7) Notify user
    notify = actions.get("notify_user")
    if notify:
        print("\n--- NOTIFY USER ---")
        print("Decision:", notify.get("decision"))
        print("Request ID:", notify.get("request_id"))
        print("Message:", notify.get("message"))
        if "justification" in notify:
            print("Justification:", notify.get("justification"))
        print("--- END NOTIFY ---\n")

    return result