from opa_client import evaluate

# Example consent records the app has
consents = {
    "alice": {"value": "yes", "withdrawn": False},
    "bob":   {"value": "yes", "withdrawn": True},
    "carol": {"value": "no",  "withdrawn": False},
}

def may_process_or_store(user_id: str) -> bool:
    input_data = {
        "user_id": user_id,
        "consents": consents,
    }

    # Call your Rego policy via OPA
    return bool(evaluate("consent/may_process_or_store", input_data))

# Example usage in app code
for user in ["alice", "bob", "carol"]:
    if may_process_or_store(user):
        print(f"{user}: OK to store/process data")
        # here the programmer would store data in DB, etc.
    else:
        print(f"{user}: NOT allowed to store/process data")
        # here the programmer would reject/log/etc.
