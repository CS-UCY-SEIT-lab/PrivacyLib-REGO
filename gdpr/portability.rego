package portability

default decision := "reject"
default justification := []
default actions := {}

# -------------------------
# Bindings
# -------------------------
portability := input.request.portability

target_user_id := portability.target_user_id
requester_user_id := portability.user_id
requested_transfer := portability.transfer_requested
transfer_service_id := portability.transfer_service_id

target_user := u if {
  u := input.users[_]
  u.id == target_user_id
}

# -------------------------
# (1) Validate request from user
# -------------------------
valid_request if {
  portability.user_id != ""
  portability.target_user_id != ""
  portability.request_id != ""
  requester_user_id == target_user_id
}

validation_reasons contains r if {
  not (portability.user_id != "")
  r := "Missing portability.user_id"
}
validation_reasons contains r if {
  not (portability.target_user_id != "")
  r := "Missing portability.target_user_id"
}
validation_reasons contains r if {
  not (portability.request_id != "")
  r := "Missing portability.request_id"
}
validation_reasons contains r if {
  portability.user_id != ""
  portability.target_user_id != ""
  portability.user_id != portability.target_user_id
  r := "Requester not authorized to request portability for another user"
}

# -------------------------
# (2) Collect all data provided or generated
# -------------------------
personal_data := obj if {
  obj := {
    "user_id": target_user.id,
    "data_items": target_user.data_items,
    "consent": input.consents[target_user.id],
    "controller": input.controller,
    "dpo": input.dpo
  }
} else := {"user_id": target_user_id, "data_items": []} if {
  true
}

# -------------------------
# (3) Format data for JSON + CSV
# NOTE: JSON content returned as an object; your Python app should json.dump it.
# -------------------------
json_filename := sprintf("portability_%v.json", [target_user_id])
csv_filename := sprintf("portability_%v.csv", [target_user_id])

json_content := personal_data

csv_content := csv if {
  header := "field,value,purpose,source,purpose_presented,restricted"
  rows := [csv_row(di) |
    di := target_user.data_items[_]
  ]
  csv := concat("\n", array.concat([header], rows))
} else := "field,value,purpose,source,purpose_presented,restricted" if {
  true
}

csv_row(di) := line if {
  f := object.get(di, "field", "")
  v := object.get(di, "value", "")
  p := object.get(di, "purpose", "")
  s := object.get(di, "source", "")
  pp := object.get(di, "purpose_presented", false)
  r := object.get(di, "restricted", false)

  # Basic CSV (no escaping); do escaping in Python if needed.
  line := sprintf("%v,%v,%v,%v,%v,%v", [f, v, p, s, pp, r])
}

# -------------------------
# (5) Optional automatic transfer
# -------------------------
service := svc if {
  requested_transfer
  svc := input.services[_]
  svc.id == transfer_service_id
}

service_compatible if {
  requested_transfer
  service.supports_portability == true
  "json" == service.supported_formats[_]
}

service_compatible if {
  requested_transfer
  service.supports_portability == true
  "csv" == service.supported_formats[_]
}

transfer_reject_reasons contains r if {
  valid_request
  requested_transfer
  not service_compatible
  r := "Transfer requested but target service is not compatible or not supported."
}

transfer_action := obj if {
  requested_transfer
  service_compatible
  obj := {
    "to_service_id": service.id,
    "to_service_name": service.name,
    "formats": {
      "json": {"filename": json_filename, "mime": "application/json"},
      "csv":  {"filename": csv_filename,  "mime": "text/csv"}
    },
    "payload": {
      "json_content": json_content,
      "csv_content": csv_content
    }
  }
} else := {} if {
  true
}

# Transfer status (replaces ternary operator)
transfer_status := "started" if {
  service_compatible
} else := "not_started" if {
  not service_compatible
}

# -------------------------
# (6) Audit log (Rego v1 style)
# -------------------------
audit_event := evt if {
  evt := {
    "type": "data_portability_request",
    "request_id": portability.request_id,
    "requester_user_id": requester_user_id,
    "target_user_id": target_user_id,
    "transfer_requested": requested_transfer,
    "transfer_service_id": transfer_service_id,
    "decision": decision
  }
}

transfer_audit_event := evt if {
  evt := {
    "type": "data_portability_transfer",
    "request_id": portability.request_id,
    "target_user_id": target_user_id,
    "to_service_id": transfer_service_id,
    "status": transfer_status
  }
}

# -------------------------
# Justification
# -------------------------
justification := js if {
  a := [x | x := validation_reasons[_]]
  b := [x | x := transfer_reject_reasons[_]]
  js := array.concat(a, b)
}

# -------------------------
# Decision
# -------------------------
decision := "accept" if { valid_request }
decision := "reject" if { not valid_request }

# -------------------------
# (4) Email user with formats (action for app)
# (5) Ask about transfer + transfer if compatible
# -------------------------
actions := out if {
  base := {
    "log_audit": audit_event,

    "present_purposes": [{"field": di.field, "purpose": di.purpose} |
      di := target_user.data_items[_]
    ],

    "downloads": [
      {"filename": json_filename, "mime": "application/json", "content": json_content},
      {"filename": csv_filename,  "mime": "text/csv",         "content": csv_content}
    ],

    "email_user": {
      "to_user_id": target_user_id,
      "subject": "Your personal data export (data portability)",
      "attachments": [json_filename, csv_filename]
    },

    "ask_transfer": {
      "requested": requested_transfer,
      "service_id": transfer_service_id
    }
  }

  decision == "accept"
  out := object.union(base, transfer_actions_block)
} else := out if {
  decision == "reject"
  out := {
    "log_audit": audit_event,
    "notify_user": {
      "decision": "reject",
      "request_id": portability.request_id,
      "justification": justification
    }
  }
}

transfer_actions_block := blk if {
  requested_transfer
  service_compatible
  blk := {
    "transfer": transfer_action,
    "log_transfer": transfer_audit_event,
    "notify_user": {
      "decision": "accept",
      "request_id": portability.request_id,
      "message": sprintf("Transfer initiated to %v.", [service.name])
    }
  }
} else := blk if {
  requested_transfer
  not service_compatible
  blk := {
    "notify_user": {
      "decision": "accept",
      "request_id": portability.request_id,
      "message": "Export created, but automatic transfer is not possible (service incompatible).",
      "transfer_issue": justification
    }
  }
} else := {} if {
  not requested_transfer
}
