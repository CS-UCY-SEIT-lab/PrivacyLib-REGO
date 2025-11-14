package consent

#
# Helper: get consent record for a user
#
consent_record(user_id) := rec if {
    key := sprintf("%v", [user_id])   # convert to string
    rec := input.consents[key]
}

#
# (1) User must have given consent
#
has_given_consent(user_id) if {
    rec := consent_record(user_id)
    rec.value == "yes"
}

#
# (2) Consent not withdrawn
#
consent_withdrawn(user_id) if {
    rec := consent_record(user_id)
    rec.withdrawn == true
}

#
# FINAL DECISION
#
may_process_or_store(user_id) if {
    has_given_consent(user_id)
    not consent_withdrawn(user_id)
}
