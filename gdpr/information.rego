package information

information(user_id) := result if {

    # -----------------------------
    # Find the user
    # -----------------------------
    some i
    user := input.users[i]
    user.id == user_id

    data_items := user.data_items

    # -----------------------------
    # Data details
    # -----------------------------
    details := [d |
        di := data_items[_]
        d := {
            "field": di.field,
            "purpose": di.purpose,
            "purpose_presented": di.purpose_presented
        }
    ]

    # -----------------------------
    # Third-party data
    # -----------------------------
    third_party := [di |
        di := data_items[_]
        di.source != "user"
    ]

    third_party_required := count(third_party) > 0

    # -----------------------------
    # Violations (MINIMAL + SAFE)
    # -----------------------------
    violations := [v |
        di := data_items[_]
        not data.lawful.lawful_purpose(di.purpose)
        v := sprintf("Unlawful purpose: %s for field %s", [di.purpose, di.field])
    ]

    # -----------------------------
    # Final result
    # -----------------------------
    result := {
        "user_id": user_id,

        "lawful_processing": data.lawful.lawful_processing(user_id),
        "consent_valid": data.consent.may_process_or_store(user_id),

        "show_controller_identity": true,
        "show_dpo_identity": true,

        "data_details": details,

        "third_party_notice": {
            "required": third_party_required,
            "data": third_party
        },

        "user_rights": [
            "access",
            "rectification",
            "erasure",
            "restriction",
            "objection",
            "data_portability"
        ],

        "show_withdraw_consent": data.consent.may_process_or_store(user_id),
        "audit_required": data.lawful.lawful_processing(user_id),

        "violations": violations
    }
}
