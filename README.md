# GDPR Policy Enforcement with OPA & Python

This project demonstrates how to implement and enforce GDPR requirements using:

- **Open Policy Agent (OPA)** with **Rego**
- A **Python client** that queries OPA over HTTP
- A structured **`input.json`** data model

The project covers the following GDPR rights and principles:

- Consent validation
- Lawful processing
- Right to Information (Articles 13 & 14)
- Right of Access (Article 15)
- Right to Rectification (Article 16)

OPA is used only for **decision-making**.  
All side effects (UI rendering, database updates, emails, downloads, logging) are handled by the application.

---

## Project Structure
```text
PrivacyLib-REGO/
│
├── gdpr/
│ ├── consent.rego
│ ├── lawful.rego
│ ├── information.rego
│ ├── access.rego
│ ├── rectification.rego
│ └── input.json
│
├── opa_client.py
├── app.py
└── README.md
└── privacyLibInputGenerator.html
```
## Requirements

- **Open Policy Agent (OPA)** (latest stable recommended)
- **Python 3.9+**
- Python dependency:
  ```bash
  pip install requests
  ```
## START OPA SERVER
  ```bash
  opa run --server --watch gdpr/
  ```
## RUNNING THE PYTHON APPLICATION
  ```bash
  python app.py
  ```
