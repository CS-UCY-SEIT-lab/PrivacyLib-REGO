import json
from opa_client import call_consent_policy, call_lawful_policy,call_information_policy,call_access_policy

with open("gdpr/input.json", "r", encoding="utf-8") as f:
    base_input = json.load(f)

def may_process_or_store(user_id: str) -> bool:
    return call_consent_policy(user_id, base_input)

def lawful_processing(user_id: str) -> bool:
    return call_lawful_policy(user_id, base_input)

'''
IM USING THE CODE BELOW TO TEST CONSENT POLICY
for uid in ["1", "2", "3"]:
    print(may_process_or_store(uid))
    if may_process_or_store(uid):
        print(f"user {uid}: OK to store/process data")
    else:
        print(f"user {uid}: NOT allowed to store/process data")
'''
'''
IM USING THE CODE BELOW TO TEST LAWFUL POLICY
for uid in ["1", "2", "3"]:
    decision = lawful_processing(uid)
    print(decision)

    if decision:
        print(f"user {uid}: LAWFUL to process/store data")
    else:
        print(f"user {uid}: NOT lawful to process/store data")
'''
'''IM USING THE CODE BELOW TO TEST INFORMATION POLICY

for uid in ["1", "2", "3"]:
        result = call_information_policy(uid, base_input)

        print(f"\n=== information report for user {uid} ===")
        if not result:
            print("No result (user not found / rule did not match).")
            continue

        # Pretty-print the JSON object returned by OPA
        print(json.dumps(result, indent=2))
'''

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
    
for uid in ["1", "2", "3"]:
    
    print(f"\n=== access response for user {uid} ===")
    access_result = call_access_policy(uid, base_input)

    if not access_result:
        print("No result (policy returned empty).")
        continue

    print(json.dumps(access_result, indent=2))
    save_access_download(access_result)