import json
from opa_client import call_consent_policy

with open("gdpr/input.json", "r", encoding="utf-8") as f:
    base_input = json.load(f)

def may_process_or_store(user_id: str) -> bool:
    return call_consent_policy(user_id, base_input)

for uid in ["1", "2", "3"]:
    print(may_process_or_store(uid))
    if may_process_or_store(uid):
        print(f"user {uid}: OK to store/process data")
    else:
        print(f"user {uid}: NOT allowed to store/process data")
