from applibrary import (apply_db_delete_plan, apply_db_update_plan, apply_processing_restriction_plan, may_process_or_store,lawful_processing, save_access_download, save_json, apply_stop_processing_plan)
from opa_client import call_access_policy, call_information_policy, call_rectification_policy, process_complaint_request, process_erasure_request, process_portability_request, process_restriction_request,process_objection_request, process_breach_assessment
import json

with open("gdpr/input.json", "r", encoding="utf-8") as f:
    base_input = json.load(f)

def testing_consent_policy():
    print("\n" + "=" * 10)
    print("CONSENT POLICY TEST")
    print("=" * 10)
    
    for uid in ["1", "2", "3"]:
        print(may_process_or_store(uid))
        if may_process_or_store(uid):
            print(f"user {uid}: OK to store/process data")
        else:
            print(f"user {uid}: NOT allowed to store/process data")
            
def testing_lawful_policy():
    print("\n" + "=" * 10)
    print("LAWFUL PROCESSING TEST")
    print("=" * 10)
    
    for uid in ["1", "2", "3"]:
        decision = lawful_processing(uid)
        print(decision)

        if decision:
            print(f"user {uid}: LAWFUL to process/store data")
        else:
            print(f"user {uid}: NOT lawful to process/store data")
            
def testing_information_policy():
    print("\n" + "=" * 10)
    print("INFORMATION POLICY TEST")
    print("=" * 10)
    
    for uid in ["1", "2", "3"]:
            result = call_information_policy(uid, base_input)

            print(f"\n=== information report for user {uid} ===")
            if not result:
                print("No result (user not found / rule did not match).")
                continue

            # Pretty-print the JSON object returned by OPA
            print(json.dumps(result, indent=2))

def testing_access_policy():
    print("\n" + "=" * 10)
    print("ACCESS POLICY REQUEST TEST")
    print("=" * 10)
    
    for uid in ["1", "2", "3"]:
    
        print(f"\n=== access response for user {uid} ===")
        access_result = call_access_policy(uid, base_input)

        if not access_result:
            print("No result (policy returned empty).")
            continue

        print(json.dumps(access_result, indent=2))
        save_access_download(access_result)

def testing_rectification_policy():
    print("\n" + "=" * 10)
    print("RECTIFICATION POLICY TEST")
    print("=" * 10)
    
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

def testing_erasure_policy():
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

def testing_restriction_policy():
    print("\n" + "=" * 10)
    print("RESTRICTION OF PROCESSING TEST")
    print("=" * 10)

    restriction_result = process_restriction_request(base_input)

    print("\n--- restriction_result (raw) ---")
    print(json.dumps(restriction_result, indent=2))

    r_decision = restriction_result.get("decision")
    r_actions = restriction_result.get("actions", {}) or {}

    if r_decision == "accept":
        stop_action = r_actions.get("stop_processing")
        if stop_action:
            updated = apply_processing_restriction_plan(base_input, stop_action)
            out_path = "outputs/input_restricted.json"
            save_json(out_path, updated)
            print(f"[+] Wrote simulated restricted input to: {out_path}")

def testing_data_portability_policy():
    print("\n==========")
    print("DATA PORTABILITY TEST")
    print("==========")

    portability_result = process_portability_request(base_input)
    print("\n--- portability_result (raw) ---")
    print(json.dumps(portability_result, indent=2))

def testing_objection_policy():
    objection_result = process_objection_request(base_input)

    print("\n--- objection_result (raw) ---")
    print(json.dumps(objection_result, indent=2))

    decision = objection_result.get("decision")
    actions = objection_result.get("actions", {}) or {}

    if decision == "accept":
        stop_action = actions.get("stop_processing")
        if stop_action:
            updated = apply_stop_processing_plan(base_input, stop_action)
            out_path = "outputs/input_objected.json"
            save_json(out_path, updated)
            print(f"[+] Wrote simulated objection-updated input to: {out_path}")
     
def testing_data_breach_notification_policy() :
     # Run breach assessment test
    result = process_breach_assessment(base_input)

    print("\n--- breach_result (raw) ---")
    print(json.dumps(result, indent=2))
    
def testing_complaint_request_policy():
    # Run complaint request test
    result = process_complaint_request(base_input)

    print("\n--- complaint_result (raw) ---")
    print(json.dumps(result, indent=2))
      
def main():
    #testing_consent_policy()
    #testing_lawful_policy()
    #testing_information_policy()
    #testing_access_policy()
    #testing_rectification_policy()
    #testing_erasure_policy()
    #testing_restriction_policy()
    #testing_data_portability_policy()
    #testing_objection_policy()
    #testing_data_breach_notification_policy()
    testing_complaint_request_policy()
    
if __name__ == "__main__":
    main()