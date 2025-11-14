package consent

# Set of users we are allowed to process
can_process contains user_id if {
    some i
    user := input.users[i]
    user.consent == true
    user_id := user.id
}

# Set of users we must NOT process (no consent or consent != true)
must_not_process contains user_id if {
    some i
    user := input.users[i]
    not user.consent
    user_id := user.id
}

# Check if a specific user has consent
has_consent(user_id) if {
    some i
    user := input.users[i]
    user.id == user_id
    user.consent == true
}
