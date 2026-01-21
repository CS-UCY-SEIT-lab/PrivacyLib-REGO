import json
from copy import deepcopy
from opa_client import call_consent_policy, call_lawful_policy,call_information_policy,call_access_policy,call_rectification_policy,process_erasure_request

def load_input(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: str, obj: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

with open("gdpr/input.json", "r", encoding="utf-8") as f:
    base_input = json.load(f)

def may_process_or_store(user_id: str) -> bool:
    return call_consent_policy(user_id, base_input)
'''
IM USING THE CODE BELOW TO TEST CONSENT POLICY
'''
for uid in ["1", "2", "3"]:
    print(may_process_or_store(uid))
    if may_process_or_store(uid):
        print(f"user {uid}: OK to store/process data")
    else:
        print(f"user {uid}: NOT allowed to store/process data")


def lawful_processing(user_id: str) -> bool:
    return call_lawful_policy(user_id, base_input)

'''
IM USING THE CODE BELOW TO TEST LAWFUL POLICY
'''
for uid in ["1", "2", "3"]:
    decision = lawful_processing(uid)
    print(decision)

    if decision:
        print(f"user {uid}: LAWFUL to process/store data")
    else:
        print(f"user {uid}: NOT lawful to process/store data")

'''IM USING THE CODE BELOW TO TEST INFORMATION POLICY
'''
for uid in ["1", "2", "3"]:
        result = call_information_policy(uid, base_input)

        print(f"\n=== information report for user {uid} ===")
        if not result:
            print("No result (user not found / rule did not match).")
            continue

        # Pretty-print the JSON object returned by OPA
        print(json.dumps(result, indent=2))


def save_access_download(access_result: dict) -> None:
    """
    access.rego returns:
      "download": { "filename": "...", "mime": "...", "content": "<json string>" }
    
    """
    dl = access_result.get("download")
    if not dl:
        return

    filename = dl.get("filename")
    content = dl.get("content")
    if not filename or not content:
        return

    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[+] Download created: {filename}")

'''IM USING THE CODE BELOW TO TEST ACCESS POLICY   
''' 
for uid in ["1", "2", "3"]:
    
    print(f"\n=== access response for user {uid} ===")
    access_result = call_access_policy(uid, base_input)

    if not access_result:
        print("No result (policy returned empty).")
        continue

    print(json.dumps(access_result, indent=2))
    save_access_download(access_result)


def apply_db_update_plan(input_data: dict, plan: list[dict]) -> dict:
    """
    OPTIONAL helper:
    Simulates updating the DB by applying updates to input_data["users"][].data_items.
    This only works if your data_items contain a "value" field.
    """
    updated = deepcopy(input_data)

    for step in plan:
        uid = step.get("user_id")
        field = step.get("field")
        new_value = step.get("new_value")

        # find user
        user = next((u for u in updated.get("users", []) if u.get("id") == uid), None)
        if not user:
            continue

        # find data_item by field
        di = next((d for d in user.get("data_items", []) if d.get("field") == field), None)
        if not di:
            continue

        # set value (if your schema supports it)
        di["value"] = new_value

    return updated

for uid in ["1", "2", "3"]:
        print("\n" + "=" * 60)
        print(f"RECTIFICATION RESPONSE FOR USER {uid}")
        print("=" * 60)

        result = call_rectification_policy(uid, base_input)

        if not result:
            print("No result (policy returned empty).")
            continue

        print(json.dumps(result, indent=2))

        plan = result.get("db_update_plan", [])
        print("\n--- db_update_plan ---")
        print(json.dumps(plan, indent=2))

        # simulation: applying the update and write a new JSON file
        if result.get("request", {}).get("validated") and plan:
            updated = apply_db_update_plan(base_input, plan)
            out_path = "gdpr/input_updated.json"
            save_json(out_path, updated)
            print(f"\n[+] Wrote simulated updated input to: {out_path}")

def apply_db_delete_plan(input_data: dict, delete_action: dict) -> dict:
    """
    Expected delete_action shape (from policy):
      {
        "target_user_id": "...",
        "fields": ["email", "age", ...]
      }
    """
    updated = deepcopy(input_data)

    target_user_id = delete_action.get("target_user_id")
    fields = set(delete_action.get("fields", []))

    if not target_user_id or not fields:
        return updated

    user = next((u for u in updated.get("users", []) if u.get("id") == target_user_id), None)
    if not user:
        return updated

    before = len(user.get("data_items", []))
    user["data_items"] = [di for di in user.get("data_items", []) if di.get("field") not in fields]
    after = len(user.get("data_items", []))

    print(f"[+] erasure delete: user={target_user_id}, removed={before - after}, remaining={after}")
    return updated


print("\n" + "=" * 10)
print("ERASURE (RIGHT TO BE FORGOTTEN) TEST")
print("=" * 10)

erasure_result = process_erasure_request(base_input)

print("\n--- erasure_result (raw) ---")
print(json.dumps(erasure_result, indent=2))

decision = erasure_result.get("decision")
actions = erasure_result.get("actions", {}) or {}

if decision == "accept":
    delete_action = actions.get("delete", {})
    if delete_action:
        updated = apply_db_delete_plan(base_input, delete_action)
        out_path = "gdpr/input_erased.json"
        save_json(out_path, updated)
        print(f"[+] Wrote simulated erased input to: {out_path}")

    tp_notes = actions.get("notify_third_parties", [])
    if tp_notes:
        print("\n--- third party notifications (simulated) ---")
        print(json.dumps(tp_notes, indent=2))
