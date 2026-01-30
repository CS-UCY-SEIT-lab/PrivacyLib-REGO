import json
from copy import deepcopy
from opa_client import (call_consent_policy, 
                        call_lawful_policy,
                        
                       )

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


def lawful_processing(user_id: str) -> bool:
    return call_lawful_policy(user_id, base_input)


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



def apply_processing_restriction_plan(input_data: dict, stop_action: dict) -> dict:
    """
    Simulates restriction by marking data_items with restricted=True.

    Expected stop_action:
      {
        "target_user_id": "...",
        "fields": ["email", "age"],
        "mode": "restrict"
      }
    """
    updated = deepcopy(input_data)

    target_user_id = stop_action.get("target_user_id")
    fields = set(stop_action.get("fields", []))
    mode = stop_action.get("mode")

    if mode != "restrict" or not target_user_id or not fields:
        return updated

    user = next((u for u in updated.get("users", []) if u.get("id") == target_user_id), None)
    if not user:
        return updated

    changed = 0
    for di in user.get("data_items", []):
        if di.get("field") in fields:
            di["restricted"] = True
            changed += 1

    print(f"[+] restriction applied: user={target_user_id}, restricted_items={changed}")
    return updated

def apply_stop_processing_plan(input_data: dict, stop_action: dict) -> dict:
    """
    Simulates "stop processing" by adding processing_stopped=True
    to affected data_items.

    Expected stop_action:
      {
        "target_user_id": "1",
        "fields": ["email","age"],
        "mode": "stop"
      }
    """
    updated = deepcopy(input_data)

    target_user_id = stop_action.get("target_user_id")
    fields = set(stop_action.get("fields", []))
    mode = stop_action.get("mode")

    if mode != "stop" or not target_user_id or not fields:
        return updated

    user = next((u for u in updated.get("users", []) if u.get("id") == target_user_id), None)
    if not user:
        return updated

    changed = 0
    for di in user.get("data_items", []):
        if di.get("field") in fields:
            di["processing_stopped"] = True
            changed += 1

    print(f"[+] objection stop-processing applied: user={target_user_id}, affected_items={changed}")
    return updated