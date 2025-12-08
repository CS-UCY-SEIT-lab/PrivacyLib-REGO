# GDPR Policy Enforcement with OPA & Python API

This project enforces **GDPR consent, lawful processing, and the Right to Information (Articles 13 & 14)** using:

- Open Policy Agent (OPA) with Rego
- A Python API client
- Structured GDPR input data

It provides:
- Consent validation
- Lawful processing validation
- Full GDPR Right-to-Information output
- A Python API that queries OPA over HTTP

---

## 📁 Project Structure
PrivacyLib-REGO/
│
├── gdpr/
│ ├── consent.rego
│ ├── lawful.rego
│ ├── information.rego
│ ├── input.json
│
├── app.py
├── opa_client.py
└── README.md

---

## Requirements

- ✅ **OPA v1.10+**
- ✅ **Python 3.9+**
- ✅ **pip**
- ✅ Python dependency:
  ```bash
  pip install requests
  cd gdpr
---
## 1.1 Run Consent Policy
  ```bash
    opa eval --format pretty --data . --input input.json 'data.consent.may_process_or_store(1)'
    opa eval --format pretty --data . --input input.json 'data.consent.may_process_or_store(2)'
    opa eval --format pretty --data . --input input.json 'data.consent.may_process_or_store(3)'
    expexted Results:
    | User | Result | Reason            |
    | ---- | ------ | ----------------- |
    | 1    | true   | Consent given     |
    | 2    | false  | Consent denied    |
    | 3    | false  | Consent withdrawn |

---

## 1.2 Run Lawful Processing Policy
    ```bash
    opa eval --format pretty --data . --input input.json 'data.lawful.lawful_processing(1)'
    opa eval --format pretty --data . --input input.json 'data.lawful.lawful_processing(2)'

---
## 1.3 Run Right-to-Information Policy (GDPR Art. 13/14)
  ```bash
  opa eval --format pretty --data . --input input.json 'data.information.information(1)'
  opa eval --format pretty --data . --input input.json 'data.information.information(2)'
