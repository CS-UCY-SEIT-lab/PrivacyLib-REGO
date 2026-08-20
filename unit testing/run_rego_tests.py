from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = ROOT / "gdpr"
BASE_INPUT = POLICY_DIR / "input.json"
FIXTURE_DIR = ROOT / "unit testing" / "inputs"


InputMutator = Callable[[dict[str, Any]], None]
Expectation = Callable[[Any], bool]


@dataclass(frozen=True)
class Case:
    article: str
    name: str
    expr: str
    expect: Expectation
    mutate: InputMutator | None = None


@dataclass(frozen=True)
class CoverageItem:
    article: str
    kind: str
    label: str
    terms: tuple[str, ...]


@dataclass(frozen=True)
class InputFixture:
    filename: str
    description: str
    mutate: InputMutator | None = None


@dataclass(frozen=True)
class CaseResult:
    ok: bool
    message: str
    case: Case
    coverage: dict[str, Any] | None = None


def at(path: str, expected: Any) -> Expectation:
    parts = path.split(".") if path else []

    def check(value: Any) -> bool:
        current = value
        for part in parts:
            if isinstance(current, list):
                current = current[int(part)]
            else:
                current = current[part]
        return current == expected

    return check


def equals(expected: Any) -> Expectation:
    return lambda value: value == expected


def contains(expected: Any) -> Expectation:
    return lambda value: expected in value


def count_is(path: str, expected: int) -> Expectation:
    parts = path.split(".") if path else []

    def check(value: Any) -> bool:
        current = value
        for part in parts:
            current = current[int(part)] if isinstance(current, list) else current[part]
        return len(current) == expected

    return check


def any_item(path: str, predicate: Callable[[Any], bool]) -> Expectation:
    parts = path.split(".") if path else []

    def check(value: Any) -> bool:
        current = value
        for part in parts:
            current = current[int(part)] if isinstance(current, list) else current[part]
        return any(predicate(item) for item in current)

    return check


def all_of(*checks: Expectation) -> Expectation:
    return lambda value: all(check(value) for check in checks)


def no_change(_: dict[str, Any]) -> None:
    return None


def user1_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return data["users"][0]["data_items"]


def user2_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return data["users"][1]["data_items"]


def set_user1_consent(value: str = "yes", withdrawn: bool = False) -> InputMutator:
    def mutate(data: dict[str, Any]) -> None:
        data["consents"]["1"] = {"value": value, "withdrawn": withdrawn}

    return mutate


def set_user1_item(index: int, **updates: Any) -> InputMutator:
    def mutate(data: dict[str, Any]) -> None:
        user1_items(data)[index].update(updates)

    return mutate


def set_request(section: str, **updates: Any) -> InputMutator:
    def mutate(data: dict[str, Any]) -> None:
        data["request"][section].update(updates)

    return mutate


def chain(*mutators: InputMutator) -> InputMutator:
    def mutate(data: dict[str, Any]) -> None:
        for mutator in mutators:
            mutator(data)

    return mutate


def remove_lawful_purpose(purpose: str) -> InputMutator:
    def mutate(data: dict[str, Any]) -> None:
        data["lawful_purposes"] = [p for p in data["lawful_purposes"] if p != purpose]

    return mutate


def set_exception(kind: str, fields: list[str]) -> InputMutator:
    def mutate(data: dict[str, Any]) -> None:
        data["exceptions"][kind] = fields

    return mutate


def add_user1_third_party_item() -> InputMutator:
    def mutate(data: dict[str, Any]) -> None:
        user1_items(data).append(
            {
                "field": "profile_score",
                "value": "42",
                "purpose": "marketing",
                "source": "1",
                "purpose_presented": True,
            }
        )

    return mutate


def set_breach(**updates: Any) -> InputMutator:
    def mutate(data: dict[str, Any]) -> None:
        data["breach"].update(updates)

    return mutate


def set_user1_first_item_purpose(purpose: str) -> InputMutator:
    return set_user1_item(0, purpose=purpose)


def remove_request_field(section: str, field: str) -> InputMutator:
    def mutate(data: dict[str, Any]) -> None:
        data["request"][section].pop(field, None)

    return mutate


CASES: list[Case] = [
    Case("consent", "consent record exists", 'data.consent.consent_record("1").value', equals("yes")),
    Case("consent", "given consent is true", 'data.consent.has_given_consent("1")', equals(True)),
    Case("consent", "missing consent is undefined", 'data.consent.has_given_consent("404")', equals(None)),
    Case("consent", "withdrawn consent is true", 'data.consent.consent_withdrawn("1")', equals(True), set_user1_consent(withdrawn=True)),
    Case("consent", "may process accepted", 'data.consent.may_process_or_store("1")', equals(True)),
    Case("consent", "may process rejects no consent", 'data.consent.may_process_or_store("1")', equals(False), set_user1_consent("no", False)),
    Case("consent", "may process rejects withdrawn", 'data.consent.may_process_or_store("1")', equals(False), set_user1_consent("yes", True)),
    Case("consent", "withdrawal confirmation completed", 'data.consent.withdrawal_confirmation("1").status', equals("completed"), set_user1_consent(withdrawn=True)),
    Case("consent", "actions expose withdrawal status", 'data.consent.actions("1").confirm_withdrawal_completion.status', equals("not_withdrawn")),

    Case("lawful", "consent dependency accepted", 'data.lawful.consent_ok("1")', equals(True)),
    Case("lawful", "consent dependency rejected", 'data.lawful.consent_ok("1")', equals(None), set_user1_consent("yes", True)),
    Case("lawful", "lawful purpose known", 'data.lawful.lawful_purpose("contract")', equals(True)),
    Case("lawful", "lawful purpose unknown", 'data.lawful.lawful_purpose("not_registered")', equals(None)),
    Case("lawful", "purpose presented", 'data.lawful.purpose_presented(input.users[0].data_items[0])', equals(True)),
    Case("lawful", "purpose not presented", 'data.lawful.purpose_presented(input.users[0].data_items[0])', equals(None), set_user1_item(0, purpose_presented=False)),
    Case("lawful", "data from user", 'data.lawful.data_from_user(input.users[0].data_items[0])', equals(True)),
    Case("lawful", "third party data not direct", 'data.lawful.data_from_user(input.users[1].data_items[0])', equals(None)),
    Case("lawful", "data item lawful", 'data.lawful.data_item_lawful(input.users[0].data_items[0])', equals(True)),
    Case("lawful", "unlawful data detected", 'data.lawful.exists_unlawful_data("1")', equals(True), set_user1_item(0, purpose="not_registered")),
    Case("lawful", "lawful processing accepted", 'data.lawful.lawful_processing("1")', equals(True)),
    Case("lawful", "lawful processing rejects withdrawn consent", 'data.lawful.lawful_processing("1")', equals(False), set_user1_consent("yes", True)),
    Case("lawful", "lawful processing rejects hidden purpose", 'data.lawful.lawful_processing("1")', equals(False), set_user1_item(0, purpose_presented=False)),
    Case("lawful", "audit logs decision", 'data.lawful.actions("1").log_audit.lawful_processing', equals(True)),

    Case("information", "third party lookup", 'data.information.third_party_by_id("1").name', equals("Third Party A")),
    Case("information", "notice uses consent and lawful dependencies", 'data.information.information("1")', all_of(at("consent_valid", True), at("lawful_processing", True))),
    Case("information", "unlawful purpose violation appears", 'data.information.information("1").violations', any_item("", lambda x: "Unlawful purpose" in x), set_user1_item(0, purpose="not_registered")),
    Case("information", "third party notice required", 'data.information.information("1").third_party_notice.required', equals(True), add_user1_third_party_item()),
    Case("information", "third party notice not required", 'data.information.information("1").third_party_notice.required', equals(False)),

    Case("access", "valid access request", 'data.access.valid_request("1")', equals(True)),
    Case("access", "invalid access request", 'data.access.valid_request("1")', equals(None), set_request("access", user_id="2")),
    Case("access", "first party item count", 'data.access.first_party_items("1")', count_is("", 2)),
    Case("access", "third party item count", 'data.access.third_party_items("1")', count_is("", 1), add_user1_third_party_item()),
    Case("access", "unknown user lookup is undefined", 'data.access.user_obj("404")', equals(None)),
    Case("access", "format first party item helper", 'data.access.format_item(input.users[0].data_items[0]).field', equals("email")),
    Case("access", "format third party item helper", 'data.access.format_tp_item(input.users[0].data_items[2]).third_party_name', equals("Third Party A"), add_user1_third_party_item()),
    Case("access", "download payload includes controller", 'data.access.download_payload("1").controller.name', equals("PrivacyLib Inc.")),
    Case("access", "download object filename", 'data.access.download_object("1").filename', equals("access_1.json")),
    Case("access", "audit record valid request true", 'data.access.audit_record("1").validated', equals(True)),
    Case("access", "audit record valid request false", 'data.access.audit_record("1").validated', equals(False), set_request("access", user_id="2")),
    Case("access", "access response accepted", 'data.access.access_response("1").request.validated', equals(True)),
    Case("access", "access response rejected", 'data.access.access_response("1").request.validated', equals(False), set_request("access", user_id="2")),
    Case("access", "third party notifications generated", 'data.access.third_party_access_notifications("1")', count_is("", 1), add_user1_third_party_item()),

    Case("rectification", "valid self request", "data.rectification.valid_request", equals(True)),
    Case("rectification", "invalid delegated request", "data.rectification.valid_request", equals(None), set_request("rectification", target_user_id="2")),
    Case("rectification", "present data includes email", 'data.rectification.present_data("1")', any_item("", lambda x: x["field"] == "email")),
    Case("rectification", "accepts editable update", 'data.rectification.accepted_updates("1")', any_item("", lambda x: x["field"] == "email")),
    Case("rectification", "rejects missing update field", 'data.rectification.rejected_updates("1")', any_item("", lambda x: x["field"] == "uknown_field")),
    Case("rectification", "rejects third party update", 'data.rectification.rejected_updates("1")', any_item("", lambda x: x["field"] == "profile_score"), chain(add_user1_third_party_item(), set_request("rectification", updates={"profile_score": "77"}))),
    Case("rectification", "response accepted", 'data.rectification.rectification_response("1").request.validated', equals(True)),
    Case("rectification", "response rejected", 'data.rectification.rectification_response("1").request.validated', equals(False), set_request("rectification", target_user_id="2")),

    Case("erasure", "accept withdrawn consent erasure", "data.erasure.decision", equals("accept"), set_exception("legal_obligation", [])),
    Case("erasure", "accept unlawfully processed erasure", "data.erasure.decision", equals("accept"), chain(set_exception("legal_obligation", []), set_request("erasure", reason="unlawfully_processed"))),
    Case("erasure", "reject unauthorized erasure", "data.erasure.decision", equals("reject"), set_request("erasure", target_user_id="2")),
    Case("erasure", "missing user id reason", "data.erasure.justification", contains("Missing erasure.user_id"), set_request("erasure", user_id="")),
    Case("erasure", "missing target user id reason", "data.erasure.justification", contains("Missing erasure.target_user_id"), set_request("erasure", target_user_id="")),
    Case("erasure", "missing request id reason", "data.erasure.justification", contains("Missing erasure.request_id"), set_request("erasure", request_id="")),
    Case("erasure", "empty fields reason", "data.erasure.justification", contains("No fields requested for erasure"), set_request("erasure", fields=[])),
    Case("erasure", "unknown target user lookup is undefined", "data.erasure.target_user", equals(None), set_request("erasure", target_user_id="404")),
    Case("erasure", "reject unsupported reason", "data.erasure.justification", any_item("", lambda x: "unsupported erasure reason" in x), chain(set_exception("legal_obligation", []), set_request("erasure", reason="unsupported"))),
    Case("erasure", "reject necessary processing", "data.erasure.justification", contains("Rejected: processing is necessary for the requested data."), chain(set_exception("legal_obligation", []), set_request("erasure", reason="objection_processing", fields=["email"]))),
    Case("erasure", "accept unnecessary objection processing", "data.erasure.decision", equals("accept"), chain(set_exception("legal_obligation", []), set_request("erasure", reason="objection_processing", fields=["age"]))),
    Case("erasure", "reject valid purpose update", "data.erasure.justification", contains("Rejected: data is mapped to a still-valid purpose."), chain(set_exception("legal_obligation", []), set_request("erasure", reason="purpose_updated", fields=["age"]))),
    Case("erasure", "accept invalid purpose update", "data.erasure.decision", equals("accept"), chain(set_exception("legal_obligation", []), set_request("erasure", reason="purpose_updated", fields=["email"]), remove_lawful_purpose("contract"))),
    Case("erasure", "legal obligation blocks deletion", "data.erasure.justification", contains("Rejected: retention required by legal obligation.")),
    Case("erasure", "public interest blocks deletion", "data.erasure.justification", contains("Rejected: retention required for public interest."), chain(set_exception("legal_obligation", []), set_exception("public_interest", ["age"]))),
    Case("erasure", "legal claims block deletion", "data.erasure.justification", contains("Rejected: retention needed to defend legal claims."), chain(set_exception("legal_obligation", []), set_exception("legal_claims", ["age"]))),
    Case("erasure", "delete plan on accept", "data.erasure.actions.delete.fields", equals(["email", "age"]), set_exception("legal_obligation", [])),

    Case("restriction", "accept inaccuracy suspicion", "data.restriction.decision", equals("accept")),
    Case("restriction", "missing user id reason", "data.restriction.justification", contains("Missing restriction.user_id"), set_request("restriction", user_id="")),
    Case("restriction", "missing target user id reason", "data.restriction.justification", contains("Missing restriction.target_user_id"), set_request("restriction", target_user_id="")),
    Case("restriction", "missing request id reason", "data.restriction.justification", contains("Missing restriction.request_id"), set_request("restriction", request_id="")),
    Case("restriction", "empty fields reason", "data.restriction.justification", contains("No fields requested for restriction"), set_request("restriction", fields=[])),
    Case("restriction", "unknown target user lookup is undefined", "data.restriction.target_user", equals(None), set_request("restriction", target_user_id="404")),
    Case("restriction", "reject corrected data", "data.restriction.justification", contains("Rejected: data was verified as correct."), set_request("restriction", checks={"data_correct": True, "purpose_valid": True, "legitimate_interest_overrides": True})),
    Case("restriction", "accept invalid purpose", "data.restriction.decision", equals("accept"), set_request("restriction", reason="invalid_purpose", checks={"data_correct": True, "purpose_valid": False, "legitimate_interest_overrides": True})),
    Case("restriction", "reject valid purpose", "data.restriction.justification", contains("Rejected: purpose is still valid."), set_request("restriction", reason="invalid_purpose", checks={"data_correct": True, "purpose_valid": True, "legitimate_interest_overrides": True})),
    Case("restriction", "accept article 21 objection", "data.restriction.decision", equals("accept"), set_request("restriction", reason="objection_art21", checks={"data_correct": True, "purpose_valid": True, "legitimate_interest_overrides": False})),
    Case("restriction", "reject article 21 override", "data.restriction.justification", contains("Rejected: controller's legitimate interests override the objection."), set_request("restriction", reason="objection_art21", checks={"data_correct": True, "purpose_valid": True, "legitimate_interest_overrides": True})),
    Case("restriction", "accept unlawfulness", "data.restriction.decision", equals("accept"), set_request("restriction", reason="unlawfulness")),
    Case("restriction", "reject unsupported reason", "data.restriction.justification", any_item("", lambda x: "unsupported restriction reason" in x), set_request("restriction", reason="unsupported")),
    Case("restriction", "reject unauthorized request", "data.restriction.decision", equals("reject"), set_request("restriction", target_user_id="2")),

    Case("portability", "valid portability request", "data.portability.valid_request", equals(True)),
    Case("portability", "missing user id reason", "data.portability.justification", contains("Missing portability.user_id"), set_request("portability", user_id="")),
    Case("portability", "missing target user id reason", "data.portability.justification", contains("Missing portability.target_user_id"), set_request("portability", target_user_id="")),
    Case("portability", "missing request id reason", "data.portability.justification", contains("Missing portability.request_id"), set_request("portability", request_id="")),
    Case("portability", "unknown target user fallback data", "data.portability.personal_data.data_items", equals([]), set_request("portability", target_user_id="404")),
    Case("portability", "consent dependency accepted", "data.portability.consent_valid", equals(True)),
    Case("portability", "lawful dependency accepted", "data.portability.lawful_processing_valid", equals(True)),
    Case("portability", "reject withdrawn consent", "data.portability.justification", contains("Rejected: consent is missing, invalid, or withdrawn."), set_user1_consent("yes", True)),
    Case("portability", "reject unlawful processing", "data.portability.justification", contains("Rejected: processing does not have a valid lawful basis."), set_user1_item(0, purpose="not_registered")),
    Case("portability", "accept export", "data.portability.decision", equals("accept")),
    Case("portability", "compatible transfer starts", "data.portability.transfer_status", equals("started")),
    Case("portability", "incompatible transfer not started", "data.portability.transfer_status", equals("not_started"), set_request("portability", transfer_service_id="missing")),
    Case("portability", "transfer not requested has empty transfer block", "data.portability.transfer_actions_block", equals({}), set_request("portability", transfer_requested=False)),
    Case("portability", "transfer warning kept with accepted export", "data.portability.actions.notify_user.transfer_issue", contains("Transfer requested but target service is not compatible or not supported."), set_request("portability", transfer_service_id="missing")),
    Case("portability", "reject unauthorized request", "data.portability.decision", equals("reject"), set_request("portability", target_user_id="2")),
    Case("portability", "legal basis contract mapping", 'data.portability.legal_basis_for_purpose("contract")', equals("contract")),
    Case("portability", "legal basis legal obligation mapping", 'data.portability.legal_basis_for_purpose("legal_obligation")', equals("legal_obligation")),
    Case("portability", "legal basis legitimate interest mapping", 'data.portability.legal_basis_for_purpose("legitimate_interest")', equals("legitimate_interest")),
    Case("portability", "legal basis public interest mapping", 'data.portability.legal_basis_for_purpose("public_interest")', equals("public_interest")),
    Case("portability", "legal basis marketing consent mapping", 'data.portability.legal_basis_for_purpose("marketing")', equals("consent")),
    Case("portability", "legal basis unknown mapping", 'data.portability.legal_basis_for_purpose("not_registered")', equals("unknown")),

    Case("objection", "accept marketing objection", "data.objection.decision", equals("accept"), set_request("objection", reason="marketing")),
    Case("objection", "missing user id reason", "data.objection.justification", contains("Missing objection.user_id"), set_request("objection", user_id="")),
    Case("objection", "missing target user id reason", "data.objection.justification", contains("Missing objection.target_user_id"), set_request("objection", target_user_id="")),
    Case("objection", "missing request id reason", "data.objection.justification", contains("Missing objection.request_id"), set_request("objection", request_id="")),
    Case("objection", "empty fields reason", "data.objection.justification", contains("No fields requested for objection"), set_request("objection", fields=[])),
    Case("objection", "unknown target user lookup is undefined", "data.objection.target_user", equals(None), set_request("objection", target_user_id="404")),
    Case("objection", "accept unnecessary legitimate interest", "data.objection.decision", equals("accept"), set_request("objection", reason="legitimate_interest", checks={"processing_is_necessary": False})),
    Case("objection", "reject necessary legitimate interest", "data.objection.justification", contains("Rejected: processing is necessary and overrides the objection (legitimate interest assessment).")),
    Case("objection", "accept unnecessary public interest", "data.objection.decision", equals("accept"), set_request("objection", reason="public_interest", checks={"processing_is_necessary": False})),
    Case("objection", "reject necessary public interest", "data.objection.justification", contains("Rejected: processing is necessary and overrides the objection (public interest assessment)."), set_request("objection", reason="public_interest", checks={"processing_is_necessary": True})),
    Case("objection", "reject unsupported reason", "data.objection.justification", any_item("", lambda x: "unsupported objection reason" in x), set_request("objection", reason="unsupported")),
    Case("objection", "reject unauthorized request", "data.objection.decision", equals("reject"), set_request("objection", target_user_id="2")),
    Case("objection", "rejected action includes complaint info", "data.objection.actions.notify_user.complaint.message", equals("If you disagree with this outcome, you can lodge a complaint with your Data Protection Authority (DPA).")),
    Case("objection", "legal basis contract mapping", 'data.objection.legal_basis_for_purpose("contract")', equals("contract")),
    Case("objection", "legal basis legal obligation mapping", 'data.objection.legal_basis_for_purpose("legal_obligation")', equals("legal_obligation")),
    Case("objection", "legal basis legitimate interest mapping", 'data.objection.legal_basis_for_purpose("legitimate_interest")', equals("legitimate_interest")),
    Case("objection", "legal basis public interest mapping", 'data.objection.legal_basis_for_purpose("public_interest")', equals("public_interest")),
    Case("objection", "legal basis marketing consent mapping", 'data.objection.legal_basis_for_purpose("marketing")', equals("consent")),
    Case("objection", "legal basis unknown mapping", 'data.objection.legal_basis_for_purpose("not_registered")', equals("unknown")),

    Case("complaint", "accept valid complaint", "data.complaint.decision", equals("accept")),
    Case("complaint", "reject missing user id", "data.complaint.justification", contains("Missing complaint.user_id"), set_request("complaint", user_id="")),
    Case("complaint", "reject unknown user", "data.complaint.justification", contains("Unknown user_id"), set_request("complaint", user_id="404")),
    Case("complaint", "reject missing description", "data.complaint.justification", contains("Missing complaint.description"), set_request("complaint", description="")),
    Case("complaint", "reject missing authority", "data.complaint.justification", contains("Missing complaint.authority_id"), set_request("complaint", authority_id="")),
    Case("complaint", "reject unknown authority", "data.complaint.justification", contains("Selected supervisory authority not found"), set_request("complaint", authority_id="missing")),
    Case("complaint", "forward accepted complaint", "data.complaint.actions.forward.authority.id", equals("cy-0000")),

    Case("breach", "notify detected high risk within 72 hours", "data.breach.decision", equals("notify_users")),
    Case("breach", "high risk rights freedoms category", "data.breach.high_risk", equals(True), set_breach(risks=["rights_freedoms"])),
    Case("breach", "high risk identity theft category", "data.breach.high_risk", equals(True), set_breach(risks=["identity_theft"])),
    Case("breach", "high risk discrimination category", "data.breach.high_risk", equals(True), set_breach(risks=["discrimination"])),
    Case("breach", "high risk financial loss category", "data.breach.high_risk", equals(True), set_breach(risks=["financial_loss"])),
    Case("breach", "high risk reputational damage category", "data.breach.high_risk", equals(True), set_breach(risks=["reputational_damage"])),
    Case("breach", "reject no breach detected", "data.breach.justification", contains("No breach detected."), set_breach(detected=False)),
    Case("breach", "reject missing incident id", "data.breach.justification", contains("Missing breach.incident_id"), set_breach(incident_id="")),
    Case("breach", "reject over 72 hours", "data.breach.justification", contains("Notification window exceeded (more than 72 hours since detection)."), set_breach(hours_since_detected=73)),
    Case("breach", "reject low risk", "data.breach.justification", contains("Risk assessment does not indicate high risk to individuals' rights and freedoms."), set_breach(risks=["minor"])),
    Case("breach", "actions notify affected users", "data.breach.actions.notify_users.users", equals(["2", "1"])),
]


EXPECTED_COVERAGE: list[CoverageItem] = [
    CoverageItem("consent", "rule", "consent_record exists and missing", ("consent record",)),
    CoverageItem("consent", "rule", "has_given_consent true and undefined", ("given consent",)),
    CoverageItem("consent", "rule", "consent_withdrawn true", ("withdrawn consent",)),
    CoverageItem("consent", "branch", "may_process_or_store accepts valid consent", ("may process accepted",)),
    CoverageItem("consent", "branch", "may_process_or_store rejects missing/no consent", ("may process rejects no consent",)),
    CoverageItem("consent", "branch", "may_process_or_store rejects withdrawn consent", ("may process rejects withdrawn",)),
    CoverageItem("consent", "branch", "withdrawal confirmation completed", ("withdrawal confirmation completed",)),
    CoverageItem("consent", "branch", "withdrawal confirmation not withdrawn", ("actions expose withdrawal status",)),

    CoverageItem("lawful", "dependency", "uses consent.may_process_or_store accepted", ("consent dependency accepted",)),
    CoverageItem("lawful", "dependency", "uses consent.may_process_or_store rejected", ("consent dependency rejected",)),
    CoverageItem("lawful", "rule", "lawful_purpose known", ("lawful purpose known",)),
    CoverageItem("lawful", "rule", "lawful_purpose unknown", ("lawful purpose unknown",)),
    CoverageItem("lawful", "rule", "purpose_presented true", ("purpose presented",)),
    CoverageItem("lawful", "rule", "purpose_presented false/undefined", ("purpose not presented",)),
    CoverageItem("lawful", "rule", "data_from_user true", ("data from user",)),
    CoverageItem("lawful", "rule", "data_from_user false/undefined", ("third party data not direct",)),
    CoverageItem("lawful", "rule", "data_item_lawful true", ("data item lawful",)),
    CoverageItem("lawful", "branch", "exists_unlawful_data true", ("unlawful data detected",)),
    CoverageItem("lawful", "branch", "lawful_processing accepts", ("lawful processing accepted",)),
    CoverageItem("lawful", "branch", "lawful_processing rejects consent failure", ("lawful processing rejects withdrawn consent",)),
    CoverageItem("lawful", "branch", "lawful_processing rejects unlawful data", ("lawful processing rejects hidden purpose",)),

    CoverageItem("information", "dependency", "uses lawful.lawful_purpose for violations", ("unlawful purpose violation",)),
    CoverageItem("information", "dependency", "uses lawful.lawful_processing and consent status", ("notice uses consent",)),
    CoverageItem("information", "branch", "third-party notice required", ("third party notice required",)),
    CoverageItem("information", "branch", "third-party notice not required", ("third party notice not required",)),
    CoverageItem("information", "rule", "controller, DPO, storage and rights notice returned", ("notice uses consent",)),

    CoverageItem("access", "branch", "valid_request true", ("valid access request",)),
    CoverageItem("access", "branch", "valid_request false/undefined", ("invalid access request",)),
    CoverageItem("access", "rule", "first_party_items", ("first party item count",)),
    CoverageItem("access", "rule", "third_party_items", ("third party item count",)),
    CoverageItem("access", "edge", "unknown user lookup undefined", ("unknown user lookup",)),
    CoverageItem("access", "rule", "format_item helper", ("format first party item",)),
    CoverageItem("access", "rule", "format_tp_item helper", ("format third party item",)),
    CoverageItem("access", "rule", "download_payload helper", ("download payload",)),
    CoverageItem("access", "rule", "download_object helper", ("download object",)),
    CoverageItem("access", "rule", "audit_record true branch", ("audit record valid request true",)),
    CoverageItem("access", "rule", "audit_record false branch", ("audit record valid request false",)),
    CoverageItem("access", "branch", "access_response accepted", ("access response accepted",)),
    CoverageItem("access", "branch", "access_response rejected", ("access response rejected",)),
    CoverageItem("access", "rule", "third_party_access_notifications", ("third party notifications generated",)),

    CoverageItem("rectification", "branch", "valid_request true", ("valid self request",)),
    CoverageItem("rectification", "branch", "valid_request false/undefined", ("invalid delegated request",)),
    CoverageItem("rectification", "rule", "present_data", ("present data",)),
    CoverageItem("rectification", "branch", "accepted editable update", ("accepts editable update",)),
    CoverageItem("rectification", "branch", "rejected missing field update", ("rejects missing update field",)),
    CoverageItem("rectification", "branch", "rejected third-party/non-editable update", ("rejects third party update",)),
    CoverageItem("rectification", "branch", "rectification_response accepted", ("response accepted",)),
    CoverageItem("rectification", "branch", "rectification_response rejected", ("response rejected",)),

    CoverageItem("erasure", "branch", "decision accept", ("accept withdrawn consent erasure",)),
    CoverageItem("erasure", "branch", "unlawfully_processed reason accepts", ("accept unlawfully processed",)),
    CoverageItem("erasure", "branch", "reject unauthorized request", ("reject unauthorized",)),
    CoverageItem("erasure", "edge", "missing user_id validation", ("missing user id",)),
    CoverageItem("erasure", "edge", "missing target_user_id validation", ("missing target user id",)),
    CoverageItem("erasure", "edge", "missing request_id validation", ("missing request id",)),
    CoverageItem("erasure", "edge", "empty fields validation", ("empty fields",)),
    CoverageItem("erasure", "edge", "unknown target user lookup", ("unknown target user lookup",)),
    CoverageItem("erasure", "branch", "reject unsupported reason", ("reject unsupported reason",)),
    CoverageItem("erasure", "branch", "reject necessary objection processing", ("reject necessary processing",)),
    CoverageItem("erasure", "branch", "accept unnecessary objection processing", ("accept unnecessary objection processing",)),
    CoverageItem("erasure", "branch", "reject valid purpose update", ("reject valid purpose update",)),
    CoverageItem("erasure", "branch", "accept invalid purpose update", ("accept invalid purpose update",)),
    CoverageItem("erasure", "branch", "legal obligation exception", ("legal obligation blocks",)),
    CoverageItem("erasure", "branch", "public interest exception", ("public interest blocks",)),
    CoverageItem("erasure", "branch", "legal claims exception", ("legal claims block",)),
    CoverageItem("erasure", "rule", "delete_plan on accept", ("delete plan on accept",)),

    CoverageItem("restriction", "branch", "accept inaccuracy suspicion", ("accept inaccuracy",)),
    CoverageItem("restriction", "edge", "missing user_id validation", ("missing user id",)),
    CoverageItem("restriction", "edge", "missing target_user_id validation", ("missing target user id",)),
    CoverageItem("restriction", "edge", "missing request_id validation", ("missing request id",)),
    CoverageItem("restriction", "edge", "empty fields validation", ("empty fields",)),
    CoverageItem("restriction", "edge", "unknown target user lookup", ("unknown target user lookup",)),
    CoverageItem("restriction", "branch", "reject corrected data", ("reject corrected",)),
    CoverageItem("restriction", "branch", "accept invalid purpose", ("accept invalid purpose",)),
    CoverageItem("restriction", "branch", "reject valid purpose", ("reject valid purpose",)),
    CoverageItem("restriction", "branch", "accept Article 21 objection", ("accept article 21",)),
    CoverageItem("restriction", "branch", "reject Article 21 override", ("reject article 21",)),
    CoverageItem("restriction", "branch", "accept unlawfulness", ("accept unlawfulness",)),
    CoverageItem("restriction", "branch", "reject unsupported reason", ("reject unsupported reason",)),
    CoverageItem("restriction", "branch", "reject unauthorized request", ("reject unauthorized request",)),

    CoverageItem("portability", "branch", "valid_request true", ("valid portability request",)),
    CoverageItem("portability", "edge", "missing user_id validation", ("missing user id",)),
    CoverageItem("portability", "edge", "missing target_user_id validation", ("missing target user id",)),
    CoverageItem("portability", "edge", "missing request_id validation", ("missing request id",)),
    CoverageItem("portability", "edge", "unknown target user fallback data", ("unknown target user fallback",)),
    CoverageItem("portability", "dependency", "uses consent.may_process_or_store", ("consent dependency",)),
    CoverageItem("portability", "dependency", "uses lawful.lawful_processing", ("lawful dependency",)),
    CoverageItem("portability", "branch", "reject withdrawn consent", ("reject withdrawn consent",)),
    CoverageItem("portability", "branch", "reject unlawful processing", ("reject unlawful processing",)),
    CoverageItem("portability", "branch", "accept export", ("accept export",)),
    CoverageItem("portability", "branch", "compatible transfer starts", ("compatible transfer starts",)),
    CoverageItem("portability", "branch", "incompatible transfer not started", ("incompatible transfer",)),
    CoverageItem("portability", "branch", "transfer not requested empty block", ("transfer not requested",)),
    CoverageItem("portability", "branch", "accepted export keeps transfer warning", ("transfer warning",)),
    CoverageItem("portability", "branch", "reject unauthorized request", ("reject unauthorized request",)),
    CoverageItem("portability", "rule", "legal basis contract mapping", ("legal basis contract",)),
    CoverageItem("portability", "rule", "legal basis legal_obligation mapping", ("legal basis legal obligation",)),
    CoverageItem("portability", "rule", "legal basis legitimate_interest mapping", ("legal basis legitimate interest",)),
    CoverageItem("portability", "rule", "legal basis public_interest mapping", ("legal basis public interest",)),
    CoverageItem("portability", "rule", "legal basis marketing/consent mapping", ("legal basis marketing consent",)),
    CoverageItem("portability", "rule", "legal basis unknown mapping", ("legal basis unknown",)),

    CoverageItem("objection", "branch", "accept marketing objection", ("accept marketing",)),
    CoverageItem("objection", "edge", "missing user_id validation", ("missing user id",)),
    CoverageItem("objection", "edge", "missing target_user_id validation", ("missing target user id",)),
    CoverageItem("objection", "edge", "missing request_id validation", ("missing request id",)),
    CoverageItem("objection", "edge", "empty fields validation", ("empty fields",)),
    CoverageItem("objection", "edge", "unknown target user lookup", ("unknown target user lookup",)),
    CoverageItem("objection", "branch", "accept unnecessary legitimate interest", ("accept unnecessary legitimate",)),
    CoverageItem("objection", "branch", "reject necessary legitimate interest", ("reject necessary legitimate",)),
    CoverageItem("objection", "branch", "accept unnecessary public interest", ("accept unnecessary public",)),
    CoverageItem("objection", "branch", "reject necessary public interest", ("reject necessary public",)),
    CoverageItem("objection", "branch", "reject unsupported reason", ("reject unsupported reason",)),
    CoverageItem("objection", "branch", "reject unauthorized request", ("reject unauthorized request",)),
    CoverageItem("objection", "dependency", "rejection exposes complaint mechanism", ("complaint info",)),
    CoverageItem("objection", "rule", "legal basis contract mapping", ("legal basis contract",)),
    CoverageItem("objection", "rule", "legal basis legal_obligation mapping", ("legal basis legal obligation",)),
    CoverageItem("objection", "rule", "legal basis legitimate_interest mapping", ("legal basis legitimate interest",)),
    CoverageItem("objection", "rule", "legal basis public_interest mapping", ("legal basis public interest",)),
    CoverageItem("objection", "rule", "legal basis marketing/consent mapping", ("legal basis marketing consent",)),
    CoverageItem("objection", "rule", "legal basis unknown mapping", ("legal basis unknown",)),

    CoverageItem("complaint", "branch", "accept valid complaint", ("accept valid complaint",)),
    CoverageItem("complaint", "branch", "reject missing user id", ("reject missing user",)),
    CoverageItem("complaint", "branch", "reject unknown user", ("reject unknown user",)),
    CoverageItem("complaint", "branch", "reject missing description", ("reject missing description",)),
    CoverageItem("complaint", "branch", "reject missing authority", ("reject missing authority",)),
    CoverageItem("complaint", "branch", "reject unknown authority", ("reject unknown authority",)),
    CoverageItem("complaint", "rule", "forward accepted complaint", ("forward accepted complaint",)),

    CoverageItem("breach", "branch", "notify detected high-risk breach within 72 hours", ("notify detected high risk",)),
    CoverageItem("breach", "edge", "high risk rights_freedoms category", ("high risk rights freedoms",)),
    CoverageItem("breach", "edge", "high risk identity_theft category", ("high risk identity theft",)),
    CoverageItem("breach", "edge", "high risk discrimination category", ("high risk discrimination",)),
    CoverageItem("breach", "edge", "high risk financial_loss category", ("high risk financial loss",)),
    CoverageItem("breach", "edge", "high risk reputational_damage category", ("high risk reputational damage",)),
    CoverageItem("breach", "branch", "reject no breach detected", ("reject no breach detected",)),
    CoverageItem("breach", "branch", "reject missing incident id", ("reject missing incident",)),
    CoverageItem("breach", "branch", "reject over 72 hours", ("reject over 72",)),
    CoverageItem("breach", "branch", "reject low risk", ("reject low risk",)),
    CoverageItem("breach", "rule", "notify affected users action", ("actions notify affected",)),
]


INPUT_FIXTURES: list[InputFixture] = [
    InputFixture(
        "valid_base.json",
        "Baseline happy-path input copied from gdpr/input.json.",
    ),
    InputFixture(
        "consent_withdrawn.json",
        "Consent dependency failure: user 1 has withdrawn consent.",
        set_user1_consent("yes", True),
    ),
    InputFixture(
        "consent_missing_or_no.json",
        "Consent dependency failure: user 1 has no affirmative consent.",
        set_user1_consent("no", False),
    ),
    InputFixture(
        "unlawful_processing_unknown_purpose.json",
        "Lawful processing failure: one data item has a purpose outside lawful_purposes.",
        set_user1_item(0, purpose="not_registered"),
    ),
    InputFixture(
        "purpose_not_presented.json",
        "Lawful processing failure: one data item was not presented to the user.",
        set_user1_item(0, purpose_presented=False),
    ),
    InputFixture(
        "third_party_notice_required.json",
        "Information/access scenario with user 1 data sourced from a third party.",
        add_user1_third_party_item(),
    ),
    InputFixture(
        "access_invalid_user.json",
        "Access request where the request user does not match the evaluated user.",
        set_request("access", user_id="2"),
    ),
    InputFixture(
        "rectification_invalid_delegated_request.json",
        "Rectification request where user 1 attempts to update user 2.",
        set_request("rectification", target_user_id="2"),
    ),
    InputFixture(
        "rectification_third_party_update.json",
        "Rectification request attempting to update a non-editable third-party field.",
        chain(add_user1_third_party_item(), set_request("rectification", updates={"profile_score": "77"})),
    ),
    InputFixture(
        "erasure_legal_obligation_exception.json",
        "Erasure request blocked by the legal-obligation retention exception.",
    ),
    InputFixture(
        "erasure_public_interest_exception.json",
        "Erasure request blocked by the public-interest retention exception.",
        chain(set_exception("legal_obligation", []), set_exception("public_interest", ["age"])),
    ),
    InputFixture(
        "erasure_legal_claims_exception.json",
        "Erasure request blocked by the legal-claims retention exception.",
        chain(set_exception("legal_obligation", []), set_exception("legal_claims", ["age"])),
    ),
    InputFixture(
        "erasure_invalid_purpose_update_accept.json",
        "Erasure purpose_updated branch where the old purpose is no longer lawful.",
        chain(set_exception("legal_obligation", []), set_request("erasure", reason="purpose_updated", fields=["email"]), remove_lawful_purpose("contract")),
    ),
    InputFixture(
        "restriction_article21_rejected.json",
        "Restriction Article 21 branch rejected because legitimate interests override.",
        set_request("restriction", reason="objection_art21", checks={"data_correct": True, "purpose_valid": True, "legitimate_interest_overrides": True}),
    ),
    InputFixture(
        "restriction_article21_accepted.json",
        "Restriction Article 21 branch accepted because legitimate interests do not override.",
        set_request("restriction", reason="objection_art21", checks={"data_correct": True, "purpose_valid": True, "legitimate_interest_overrides": False}),
    ),
    InputFixture(
        "portability_incompatible_transfer.json",
        "Portability export accepted, but automatic transfer service is incompatible/missing.",
        set_request("portability", transfer_service_id="missing"),
    ),
    InputFixture(
        "portability_withdrawn_consent_rejected.json",
        "Portability rejected through the reused consent rule.",
        set_user1_consent("yes", True),
    ),
    InputFixture(
        "portability_unlawful_processing_rejected.json",
        "Portability rejected through the reused lawful-processing rule.",
        set_user1_item(0, purpose="not_registered"),
    ),
    InputFixture(
        "objection_marketing_accepted.json",
        "Objection accepted for direct marketing.",
        set_request("objection", reason="marketing"),
    ),
    InputFixture(
        "objection_legitimate_interest_rejected.json",
        "Objection rejected because processing is necessary.",
    ),
    InputFixture(
        "objection_public_interest_accepted.json",
        "Objection accepted because public-interest processing is not necessary.",
        set_request("objection", reason="public_interest", checks={"processing_is_necessary": False}),
    ),
    InputFixture(
        "complaint_invalid_authority.json",
        "Complaint rejected because the selected supervisory authority is unknown.",
        set_request("complaint", authority_id="missing"),
    ),
    InputFixture(
        "complaint_missing_description.json",
        "Complaint rejected because the description is missing.",
        set_request("complaint", description=""),
    ),
    InputFixture(
        "breach_low_risk.json",
        "Breach detected within 72 hours but no high-risk category is present.",
        set_breach(risks=["minor"]),
    ),
    InputFixture(
        "breach_over_72_hours.json",
        "Breach detected with high risk but outside the 72-hour notification window.",
        set_breach(hours_since_detected=73),
    ),
    InputFixture(
        "breach_missing_incident_id.json",
        "Breach input missing the required incident_id.",
        set_breach(incident_id=""),
    ),
]


def load_base_input() -> dict[str, Any]:
    with BASE_INPUT.open(encoding="utf-8") as handle:
        return json.load(handle)


def materialize_input_fixtures(base_input: dict[str, Any]) -> list[Path]:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for fixture in INPUT_FIXTURES:
        data = copy.deepcopy(base_input)
        if fixture.mutate is not None:
            fixture.mutate(data)

        path = FIXTURE_DIR / fixture.filename
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        written.append(path)

    return written


def opa_eval(expr: str, input_data: dict[str, Any]) -> tuple[Any, dict[str, Any] | None]:
    opa = shutil.which("opa")
    if opa is None:
        raise RuntimeError("OPA executable not found on PATH.")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(input_data, handle)
        input_path = Path(handle.name)

    try:
        completed = subprocess.run(
            [
                opa,
                "eval",
                "--format",
                "json",
                "--data",
                str(POLICY_DIR),
                "--input",
                str(input_path),
                expr,
            ],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
    finally:
        input_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())

    payload = json.loads(completed.stdout)
    coverage = payload.get("coverage")
    results = payload.get("result", [])
    if not results:
        return None, coverage

    expressions = results[0].get("expressions", [])
    if not expressions:
        return None, coverage

    return expressions[0].get("value"), coverage


def run_case(case: Case, base_input: dict[str, Any]) -> CaseResult:
    data = copy.deepcopy(base_input)
    if case.mutate is not None:
        case.mutate(data)

    try:
        value, coverage = opa_eval(case.expr, data)
    except Exception as exc:
        return CaseResult(False, f"{case.article} / {case.name}: evaluation error: {exc}", case)

    try:
        passed = case.expect(value)
    except Exception as exc:
        return CaseResult(False, f"{case.article} / {case.name}: expectation error: {exc}; value={value!r}", case, coverage)

    if passed:
        return CaseResult(True, f"PASS {case.article} / {case.name}", case, coverage)
    return CaseResult(False, f"FAIL {case.article} / {case.name}: expr={case.expr}; value={value!r}", case, coverage)


def matches_coverage_item(case: Case, item: CoverageItem) -> bool:
    haystack = f"{case.name} {case.expr}".lower()
    return case.article == item.article and all(term.lower() in haystack for term in item.terms)


def print_scenario_coverage(results: list[CaseResult]) -> bool:
    passing_cases = [result.case for result in results if result.ok]
    missing: list[CoverageItem] = []

    print("\nScenario coverage checklist:")
    for item in EXPECTED_COVERAGE:
        covered = any(matches_coverage_item(case, item) for case in passing_cases)
        mark = "PASS" if covered else "MISS"
        print(f"{mark} {item.article} / {item.kind} / {item.label}")
        if not covered:
            missing.append(item)

    total = len(EXPECTED_COVERAGE)
    covered_count = total - len(missing)
    print(f"\nScenario coverage result: {covered_count}/{total} expected items covered")
    return not missing


def add_range(lines: set[int], item: dict[str, Any]) -> None:
    start = item.get("start", {}).get("row")
    end = item.get("end", {}).get("row", start)
    if isinstance(start, int) and isinstance(end, int):
        lines.update(range(start, end + 1))


def collect_coverage_lines(coverage: dict[str, Any] | None, key: str) -> dict[str, set[int]]:
    collected: dict[str, set[int]] = {}
    if not coverage:
        return collected

    for item in coverage.get(key, []):
        file_name = item.get("file")
        if isinstance(file_name, str):
            collected.setdefault(file_name, set())
            add_range(collected[file_name], item)

    for file_name, file_coverage in coverage.get("files", {}).items():
        if isinstance(file_coverage, dict):
            for item in file_coverage.get(key, []):
                collected.setdefault(file_name, set())
                add_range(collected[file_name], item)

    return collected


def merge_coverage(results: list[CaseResult], key: str) -> dict[str, set[int]]:
    merged: dict[str, set[int]] = {}
    for result in results:
        if not result.ok:
            continue
        for file_name, lines in collect_coverage_lines(result.coverage, key).items():
            merged.setdefault(file_name, set()).update(lines)
    return merged


def collect_coverage_counts(coverage: dict[str, Any] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not coverage:
        return counts

    for file_name, file_coverage in coverage.get("files", {}).items():
        if isinstance(file_coverage, dict):
            covered_lines = file_coverage.get("covered_lines", 0)
            if isinstance(covered_lines, int):
                counts[file_name] = max(counts.get(file_name, 0), covered_lines)

    return counts


def merge_coverage_counts(results: list[CaseResult]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for result in results:
        if not result.ok:
            continue
        for file_name, count in collect_coverage_counts(result.coverage).items():
            merged[file_name] = max(merged.get(file_name, 0), count)
    return merged


def policy_line_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in POLICY_DIR.glob("*.rego"):
        counts[str(path)] = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        counts[path.name] = counts[str(path)]
    return counts


def print_line_coverage(results: list[CaseResult]) -> None:
    covered = merge_coverage(results, "covered")
    fallback_counts = merge_coverage_counts(results)
    counts = policy_line_counts()
    if not covered and not fallback_counts:
        print("\nOPA line coverage: unavailable in this OPA JSON output.")
        return

    print("\nOPA line coverage from passing scenarios:")
    total_covered = 0
    total_lines = 0
    for path in sorted(POLICY_DIR.glob("*.rego")):
        relative_name = f"gdpr\\{path.name}"
        keys = [
            str(path),
            path.name,
            str(path).replace("\\", "/"),
            relative_name,
            relative_name.replace("\\", "/"),
        ]
        file_covered = set()
        for key in keys:
            file_covered.update(covered.get(key, set()))
        fallback_count = max(fallback_counts.get(key, 0) for key in keys)
        line_count = counts[str(path)]
        covered_count = max(len(file_covered), fallback_count)
        total_covered += covered_count
        total_lines += line_count
        percent = (covered_count / line_count * 100) if line_count else 100
        print(f"{path.name}: {covered_count}/{line_count} non-empty lines touched ({percent:.1f}%)")

    if total_lines:
        print(f"Total touched lines: {total_covered}/{total_lines} ({total_covered / total_lines * 100:.1f}%)")


def main() -> int:
    base_input = load_base_input()
    fixtures = materialize_input_fixtures(base_input)
    failures: list[str] = []
    results: list[CaseResult] = []
    passed = 0

    print(f"Wrote {len(fixtures)} representative input JSON files to {FIXTURE_DIR}")
    print(f"Running {len(CASES)} Rego unit cases against {POLICY_DIR}")
    print("Each case loads the full gdpr bundle so cross-article rule reuse is tested.\n")

    for case in CASES:
        result = run_case(case, base_input)
        results.append(result)
        print(result.message)
        if result.ok:
            passed += 1
        else:
            failures.append(result.message)

    print(f"\nResult: {passed}/{len(CASES)} passed")
    scenario_coverage_ok = print_scenario_coverage(results)
    print("\nNote: this checklist proves the expected rule, branch, and dependency scenarios are represented.")
    print("It does not claim the input space has only this many mathematical combinations.")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    if not scenario_coverage_ok:
        print("\nMissing scenario coverage means there are expected branches without passing tests.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
