package lawful

#
# (1) Obtain consent from the user
# We reuse your existing consent policy:
#   data.consent.may_process_or_store(user_id)
#

consent_ok(user_id) if {
    data.consent.may_process_or_store(user_id)
}

#
# (2) Ensure the processing is lawful
#  -> the purpose must be in the list of lawful purposes
#
lawful_purpose(purpose) if {
    some i
    input.lawful_purposes[i] == purpose
}

#
# (3) check if system has presented the purpose of processing to the user
# We assume each data item has "purpose_presented": true
#
purpose_presented(di) if {
    di.purpose_presented == true
}

#
# (4) Gather the data from the user
# We assume each data item has "source": "user" when it comes directly from the user
#
data_from_user(di) if {
    di.source == "user"
}

#
# Helper: all data items for a given user
#
user_data_item(user_id, di) if {
    some i, j
    u := input.users[i]
    u.id == user_id
    d := u.data_items[j]   # local variable
    di == d                # unify di with d (no reassign)
}

#
# A single data item is processed lawfully if:
#   - its purpose is lawful
#   - the purpose was presented to the user
#   - the data was gathered from the user
#
data_item_lawful(di) if {
    lawful_purpose(di.purpose)
    purpose_presented(di)
    data_from_user(di)
}

#
# check if there is any data item for this user that is NOT lawful
#
exists_unlawful_data(user_id) if {
    some i, j
    u := input.users[i]
    u.id == user_id
    di := u.data_items[j]
    not data_item_lawful(di)
}

#
# FINAL DECISION:
# Lawful processing for this user iff:
#   (1) consent_ok
#   AND
#   (2-4) no unlawful data items
#
lawful_processing(user_id) if {
    consent_ok(user_id)
    not exists_unlawful_data(user_id)
}

