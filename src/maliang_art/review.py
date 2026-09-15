#!/usr/bin/env python3
"""Deterministic core for multimodal artwork review.

This module deliberately has no filesystem, store, image, network, OAuth, or
model-call dependencies. Callers bind and verify artifacts before passing
records here; these helpers validate authority and compile immutable payloads.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1
REVIEW_DECISIONS = ("retry", "escalate_to_human", "pass_to_human")
RULE_AUTHORITIES = ("hard", "advisory", "human-only")
RULE_LIFECYCLES = ("draft", "active", "superseded", "suspended")
QUALIFICATION_STATES = ("unqualified", "shadow", "auto-retry-qualified", "suspended", "superseded")
CASE_STATUSES = ("active", "shadow-only", "needs-splitting", "historical-only", "superseded", "invalid")
CASE_POLARITIES = ("positive", "negative", "boundary")
_APPROVING_DECISIONS = frozenset({"approved", "passed"})
_REJECTING_DECISIONS = frozenset({"rejected", "superseded", "retry"})
_HUMAN_DECISIONS = _APPROVING_DECISIONS | _REJECTING_DECISIONS
CONTROLLED_OPERATIONS = ("remove", "enforce", "adjust", "preserve", "hide", "restore_from_anchor")
GENERATION_INPUT_ROLES = (
    "POSITIVE_IDENTITY_ANCHOR", "APPROVED_COMPONENT", "APPROVED_TOPOLOGY_COMPARISON",
)
NEGATIVE_ROLES = ("NEGATIVE_REVIEW_ONLY", "FORBIDDEN_GENERATION_INPUT")
SEMANTIC_EVIDENCE_ROLES = GENERATION_INPUT_ROLES + NEGATIVE_ROLES
SCOPE_FIELDS = ("project", "family", "topology", "direction", "view", "pose", "equipmentCategory", "equipmentState", "assetId")
EXPERIENCE_ACTIONS = ("add-case", "narrow-scope", "scoped-exception", "draft-rule", "human-only", "reject-learning")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_EVIDENCE_ROLE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ATTEMPT_RE = re.compile(r".+-a(\d{3,})$")


class ReviewValidationError(ValueError):
    """Raised when a review record violates schema or authority boundaries."""


@dataclass(frozen=True)
class ReviewAuthority:
    """Explicit human-authority identity for project-specific decisions."""

    reviewer: str

    def __post_init__(self) -> None:
        if not isinstance(self.reviewer, str) or not self.reviewer.strip():
            raise ReviewValidationError("authority reviewer must be non-empty text")


def canonical_bytes(value: Any) -> bytes:
    """Return the repository's canonical JSON encoding for a JSON value."""
    _assert_json_value(value, "value")
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def stable_id(prefix: str, payload: Any, length: int = 16) -> str:
    if not isinstance(prefix, str) or not prefix or not re.fullmatch(r"[a-z0-9-]+", prefix):
        raise ReviewValidationError("prefix must be non-empty lower kebab case")
    if not isinstance(length, int) or isinstance(length, bool) or not 8 <= length <= 64:
        raise ReviewValidationError("length must be an integer from 8 through 64")
    return f"{prefix}-{hashlib.sha256(canonical_bytes(payload)).hexdigest()[:length]}"


def derive_review_history_index_entry(
    feedback: Mapping[str, Any], *, attempt: Mapping[str, Any] | None = None,
    approval: Mapping[str, Any] | None = None, verdict: Mapping[str, Any] | None = None,
    artifact: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive a read-only, stable history row from already-loaded records."""
    feedback = _mapping(feedback, "feedback")
    feedback_id = _required_text(feedback, "feedbackId")
    attempt_id = _required_text(feedback, "attemptId")
    if attempt is not None and _required_text(_mapping(attempt, "attempt"), "attemptId") != attempt_id:
        raise ReviewValidationError("attempt does not match feedback attemptId")
    for name, record in (("approval", approval), ("verdict", verdict)):
        if record is not None and record.get("attemptId") != attempt_id:
            raise ReviewValidationError(f"{name} does not match feedback attemptId")
    bound_artifact = artifact or ((attempt or {}).get("artifacts", {}).get("calibrated") if attempt else None)
    if bound_artifact is None and attempt:
        bound_artifact = (attempt.get("artifacts", {}).get("prepared") or attempt.get("artifacts", {}).get("raw"))
    artifact_value = _artifact(bound_artifact, "artifact") if bound_artifact is not None else None
    categories = sorted(_unique_text_list(feedback.get("categories", []), "feedback.categories"))
    payload = {
        "feedbackId": feedback_id, "attemptId": attempt_id,
        "jobId": feedback.get("jobId") or (attempt or {}).get("jobId"),
        "authorType": feedback.get("authorType"), "reviewer": feedback.get("reviewer"),
        "disposition": feedback.get("disposition") or feedback.get("verdict"),
        "categories": categories, "artifact": artifact_value,
        "approvalId": (approval or {}).get("approvalId"),
        "approvalDecision": (approval or {}).get("decision"),
        "verdictId": (verdict or {}).get("artDirectionVerdictId") or (verdict or {}).get("verdictId"),
        "verdictDecision": (verdict or {}).get("decision"),
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    return {"schemaVersion": SCHEMA_VERSION, "historyEntryId": stable_id("review-history", payload), **payload}


def audit_case_fitness(case: Mapping[str, Any], *, authority: ReviewAuthority) -> dict[str, Any]:
    """Classify a prospective case against explicit human authority."""
    case = _mapping(case, "case")
    reasons: list[str] = []
    fatal: list[str] = []
    polarity = case.get("polarity")
    source = case.get("source", {})
    artifact = case.get("artifact")
    if polarity not in CASE_POLARITIES:
        fatal.append("invalid_polarity")
    try:
        _artifact(artifact, "case.artifact")
    except ReviewValidationError:
        fatal.append("invalid_artifact_binding")
    if not isinstance(source, Mapping):
        fatal.append("missing_attempt_or_human_decision")
        source = {}
    elif not source.get("attemptId") or not source.get("humanDecision"):
        fatal.append("missing_attempt_or_human_decision")
    if source.get("reviewer") != authority.reviewer:
        fatal.append("non_authoritative_human_source")
    decision = source.get("humanDecision")
    if decision not in _HUMAN_DECISIONS:
        fatal.append("invalid_human_decision")
    if polarity == "positive" and decision not in _APPROVING_DECISIONS:
        fatal.append("positive_not_approved")
    if polarity == "negative" and decision not in _REJECTING_DECISIONS:
        fatal.append("negative_not_rejected")
    scope = case.get("scope")
    if not isinstance(scope, Mapping) or not scope:
        fatal.append("machine_readable_scope_missing")
    if case.get("containsRetiredAsset") is True:
        fatal.append("retired_asset_reference")
    if case.get("supersededBy"):
        reasons.append("superseded_by_later_knowledge")
    defects = case.get("defectIds", [])
    if not isinstance(defects, list) or any(not isinstance(value, str) or not value for value in defects):
        fatal.append("invalid_defect_ids")
    elif len(defects) > 1 and not case.get("atomicEvidenceRegion"):
        reasons.append("inseparable_multiple_defects")
    if case.get("comparable") is False:
        reasons.append("not_comparable")
    if case.get("observableAtReviewSize") is not True:
        reasons.append("not_observable_at_review_size")
    if case.get("crossAsset") is True and not case.get("referenceResponsibility"):
        reasons.append("cross_asset_responsibility_missing")
    if polarity == "negative" and case.get("reviewOnly") is not True:
        fatal.append("negative_not_review_only")
    if case.get("hashVerified") is False or case.get("artifactExists") is False:
        fatal.append("artifact_or_hash_invalid")
    requested = case.get("status")
    if fatal:
        status = "invalid"
    elif case.get("supersededBy"):
        status = "superseded"
    elif "inseparable_multiple_defects" in reasons:
        status = "needs-splitting"
    elif "not_observable_at_review_size" in reasons or "not_comparable" in reasons:
        status = "historical-only"
    elif "cross_asset_responsibility_missing" in reasons or requested == "shadow-only":
        status = "shadow-only"
    else:
        status = "active"
    return {"status": status, "eligibleForActivePolicy": status == "active", "reasons": fatal + reasons}


def validate_review_rule(rule: Mapping[str, Any]) -> dict[str, Any]:
    rule = deepcopy(dict(_mapping(rule, "rule")))
    _only_keys(rule, {"schemaVersion", "ruleId", "version", "scope", "authority", "autoRetryEligible", "requiredEvidenceRoles", "sources", "positiveCaseIds", "negativeCaseIds", "supersedes", "lifecycle", "statement"}, "rule")
    _required_text(rule, "ruleId"); _positive_int(rule.get("version"), "rule.version")
    _validate_scope(rule.get("scope", {}), "rule.scope")
    if rule.get("authority") not in RULE_AUTHORITIES:
        raise ReviewValidationError("rule.authority is invalid")
    if not isinstance(rule.get("autoRetryEligible"), bool):
        raise ReviewValidationError("rule.autoRetryEligible must be boolean")
    if rule["autoRetryEligible"] and rule["authority"] != "hard":
        raise ReviewValidationError("only hard rules may request automatic retry eligibility")
    roles = _unique_text_list(rule.get("requiredEvidenceRoles", []), "rule.requiredEvidenceRoles")
    if any(not _EVIDENCE_ROLE_RE.fullmatch(role) for role in roles):
        raise ReviewValidationError("rule contains an invalid evidence role")
    sources = rule.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ReviewValidationError("rule.sources must be a non-empty list")
    for index, source in enumerate(sources):
        source = _mapping(source, f"rule.sources[{index}]")
        _required_text(source, "type"); _required_text(source, "id")
    for key in ("positiveCaseIds", "negativeCaseIds"):
        _unique_text_list(rule.get(key, []), f"rule.{key}")
    if rule.get("lifecycle", "active") not in RULE_LIFECYCLES:
        raise ReviewValidationError("rule.lifecycle is invalid")
    if "schemaVersion" in rule and rule["schemaVersion"] != SCHEMA_VERSION:
        raise ReviewValidationError("unsupported rule schemaVersion")
    return rule


def validate_review_case(case: Mapping[str, Any], *, authority: ReviewAuthority) -> dict[str, Any]:
    case = deepcopy(dict(_mapping(case, "case")))
    _only_keys(case, {"schemaVersion", "caseId", "version", "ruleIds", "polarity", "status", "scope", "artifact", "source", "reviewOnly", "generationInputAllowed", "evidenceRegion", "supersedes", "referenceResponsibility", "comparable", "observableAtReviewSize", "crossAsset", "atomicEvidenceRegion", "hashVerified", "artifactExists", "containsRetiredAsset", "supersededBy", "defectIds"}, "case")
    _required_text(case, "caseId"); _positive_int(case.get("version"), "case.version")
    _unique_text_list(case.get("ruleIds"), "case.ruleIds", nonempty=True)
    if case.get("polarity") not in CASE_POLARITIES or case.get("status") not in CASE_STATUSES:
        raise ReviewValidationError("case polarity or status is invalid")
    _validate_scope(case.get("scope", {}), "case.scope")
    _artifact(case.get("artifact"), "case.artifact")
    source = _mapping(case.get("source"), "case.source")
    _required_text(source, "attemptId"); decision = _required_text(source, "humanDecision")
    if source.get("reviewer") != authority.reviewer:
        raise ReviewValidationError("case source must match the configured authority reviewer")
    if decision not in _HUMAN_DECISIONS:
        raise ReviewValidationError("case source humanDecision is invalid")
    if case["polarity"] == "positive" and decision not in _APPROVING_DECISIONS:
        raise ReviewValidationError("positive cases require an approving human decision")
    if case["polarity"] == "negative" and decision not in _REJECTING_DECISIONS:
        raise ReviewValidationError("negative cases require a rejecting human decision")
    if not isinstance(case.get("reviewOnly"), bool) or not isinstance(case.get("generationInputAllowed"), bool):
        raise ReviewValidationError("case reviewOnly and generationInputAllowed must be boolean")
    if case["polarity"] == "negative" and not case["reviewOnly"]:
        raise ReviewValidationError("negative cases must be review-only")
    if case["generationInputAllowed"] and (case["polarity"] != "positive" or case["reviewOnly"]):
        raise ReviewValidationError("only positive, non-review-only cases may be generation inputs")
    if case["status"] != "active" and case["generationInputAllowed"]:
        raise ReviewValidationError("inactive cases cannot be generation inputs")
    if "schemaVersion" in case and case["schemaVersion"] != SCHEMA_VERSION:
        raise ReviewValidationError("unsupported case schemaVersion")
    return case


def scope_matches(scope: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    scope = _validate_scope(scope, "scope")
    context = _mapping(context, "context")
    for field, expected in scope.items():
        actual = context.get(field)
        accepted = expected if isinstance(expected, list) else [expected]
        if "*" not in accepted and actual not in accepted:
            return False
    return True


def compile_review_policy(
    project_policy: Mapping[str, Any], rules: Sequence[Mapping[str, Any]], cases: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any], *, authority: ReviewAuthority,
    acceptance_case_ids: Sequence[str] = (), feedback_rule_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Select and freeze the applicable active policy; conflicts hard-fail."""
    project_policy = deepcopy(dict(_mapping(project_policy, "projectPolicy")))
    policy_id = _required_text(project_policy, "policyId")
    policy_version = _positive_int(project_policy.get("version"), "projectPolicy.version")
    context_copy = deepcopy(dict(_mapping(context, "context")))
    selected_rules = [validate_review_rule(value) for value in rules]
    selected_rules = [r for r in selected_rules if r.get("lifecycle", "active") == "active" and scope_matches(r["scope"], context_copy)]
    requested = set(_unique_text_list(feedback_rule_ids, "feedbackRuleIds"))
    missing_feedback = requested - {r["ruleId"] for r in selected_rules}
    if missing_feedback:
        raise ReviewValidationError(f"feedback references inapplicable or missing rules: {sorted(missing_feedback)}")
    by_id: dict[str, dict[str, Any]] = {}
    for rule in selected_rules:
        old = by_id.get(rule["ruleId"])
        if old and (old["version"] != rule["version"] or old != rule):
            raise ReviewValidationError(f"conflicting active rule versions: {rule['ruleId']}")
        by_id[rule["ruleId"]] = rule
    ordered_rules = sorted(by_id.values(), key=lambda r: (_scope_specificity(r["scope"]), r["ruleId"], r["version"]), reverse=True)
    valid_cases = [validate_review_case(value, authority=authority) for value in cases]
    selected_case_ids = set(_unique_text_list(acceptance_case_ids, "acceptanceCaseIds"))
    selected_cases = []
    active_rule_ids = {r["ruleId"] for r in ordered_rules}
    for case in valid_cases:
        if case["status"] not in {"active", "shadow-only"}:
            continue
        if not scope_matches(case["scope"], context_copy):
            continue
        if not active_rule_ids.intersection(case["ruleIds"]) and case["caseId"] not in selected_case_ids:
            continue
        selected_cases.append(case)
    missing_cases = selected_case_ids - {c["caseId"] for c in selected_cases}
    if missing_cases:
        raise ReviewValidationError(f"required acceptance cases are missing or inapplicable: {sorted(missing_cases)}")
    for case in selected_cases:
        if case["polarity"] == "negative" and case["generationInputAllowed"]:
            raise ReviewValidationError("negative case selected as generation input")
    payload = {
        "projectPolicy": {"policyId": policy_id, "version": policy_version},
        "context": context_copy,
        "rules": ordered_rules,
        "cases": sorted(selected_cases, key=lambda c: (c["caseId"], c["version"])),
        "acceptanceCaseIds": sorted(selected_case_ids),
        "feedbackRuleIds": sorted(requested),
    }
    digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    return {"schemaVersion": SCHEMA_VERSION, "compiledPolicyId": stable_id("compiled-review-policy", payload), "sha256": digest, **payload}


def review_effort(generation_round: int | str, *, qualification_mode: bool = False, technical_remediation: bool = False) -> str:
    """Map the non-technical generation round to the fixed Reviewer effort."""
    if qualification_mode:
        raise ReviewValidationError("qualification/shadow evaluation is not a formal generation round")
    if technical_remediation:
        raise ReviewValidationError("technical remediation does not consume or define a generation round")
    if isinstance(generation_round, str):
        match = _ATTEMPT_RE.fullmatch(generation_round)
        if not match:
            raise ReviewValidationError("attempt id must end in -aNNN")
        generation_round = int(match.group(1))
    if isinstance(generation_round, bool) or generation_round not in {1, 2, 3}:
        raise ReviewValidationError("automatic model review supports generation rounds 1 through 3 only")
    return {1: "medium", 2: "high", 3: "xhigh"}[generation_round]


def build_model_review_packet(
    *, attempt: Mapping[str, Any], contract: Mapping[str, Any], brief: Mapping[str, Any],
    compiled_policy: Mapping[str, Any], artifacts: Mapping[str, Mapping[str, Any]], evidence: Sequence[Mapping[str, Any]],
    acceptance_cases: Sequence[Mapping[str, Any]], feedback: Sequence[Mapping[str, Any]], frozen_invariants: Sequence[str],
    required_model: str, review_round: int | None = None,
) -> dict[str, Any]:
    attempt = _mapping(attempt, "attempt"); contract = _mapping(contract, "contract"); brief = _mapping(brief, "brief")
    attempt_id = _required_text(attempt, "attemptId")
    round_number = review_round
    if round_number is None:
        match = _ATTEMPT_RE.fullmatch(attempt_id)
        if not match:
            raise ReviewValidationError("cannot derive review round from attemptId")
        round_number = int(match.group(1))
    effort = review_effort(round_number)
    artifact_list = [{"role": role, **_artifact(value, f"artifacts.{role}")} for role, value in sorted(_mapping(artifacts, "artifacts").items())]
    evidence_list = [_validate_evidence(item, f"evidence[{i}]") for i, item in enumerate(evidence)]
    for item in evidence_list:
        if item["role"] in NEGATIVE_ROLES and item.get("generationInput") is True:
            raise ReviewValidationError("negative/review-only evidence cannot be a generation input")
    policy = _mapping(compiled_policy, "compiledPolicy")
    payload = {
        "schemaVersion": SCHEMA_VERSION, "attemptId": attempt_id,
        "contract": _record_binding(contract, "contractId", "contract"),
        "brief": _record_binding(brief, "briefId", "brief"),
        "compiledPolicy": {"compiledPolicyId": _required_text(policy, "compiledPolicyId"), "sha256": _sha(policy.get("sha256"), "compiledPolicy.sha256")},
        "reviewRound": round_number, "requiredModel": _text(required_model, "requiredModel"), "reasoningEffort": effort,
        "artifacts": artifact_list, "evidence": evidence_list,
        "acceptanceCases": deepcopy(list(acceptance_cases)), "feedback": deepcopy(list(feedback)),
        "frozenInvariants": _unique_text_list(frozen_invariants, "frozenInvariants"),
        "permissions": {"allowedDecisions": list(REVIEW_DECISIONS), "mayApprove": False, "mayMakeHumanDecision": False, "mayUseAggregateAestheticScore": False},
    }
    packet_id = stable_id("model-review-packet", payload)
    packet = {"packetId": packet_id, **payload}
    packet["sha256"] = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    return validate_model_review_packet(packet)


def build_shadow_model_review_packet(
    *, attempt: Mapping[str, Any], contract: Mapping[str, Any], brief: Mapping[str, Any],
    compiled_policy: Mapping[str, Any], case_binding: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]],
    frozen_invariants: Sequence[str], required_model: str, requested_effort: str,
    historical_contract: Mapping[str, Any] | None = None,
    compiled_policy_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Freeze one historical human-labelled case for non-authoritative Shadow review."""
    if requested_effort not in {"medium", "high", "xhigh"}:
        raise ReviewValidationError("shadow requested effort must be medium, high, or xhigh")
    attempt = _mapping(attempt, "attempt")
    case_binding = deepcopy(dict(_mapping(case_binding, "caseBinding")))
    _only_keys(case_binding, {"reviewCaseRecord", "caseId", "artifact", "humanDecision", "humanFeedback", "evidenceRegion"}, "caseBinding")
    _require_keys(case_binding, {"reviewCaseRecord", "caseId", "artifact", "humanDecision", "humanFeedback", "evidenceRegion"}, "caseBinding")
    normalized_case = {
        "reviewCaseRecord": _record_binding(case_binding["reviewCaseRecord"], "reviewCaseRecordId", "caseBinding.reviewCaseRecord"),
        "caseId": _text(case_binding["caseId"], "caseBinding.caseId"),
        "artifact": _artifact(case_binding["artifact"], "caseBinding.artifact"),
        "humanDecision": _text(case_binding["humanDecision"], "caseBinding.humanDecision"),
        "humanFeedback": _record_binding(case_binding["humanFeedback"], "feedbackId", "caseBinding.humanFeedback"),
        "evidenceRegion": _region(case_binding["evidenceRegion"], "caseBinding.evidenceRegion"),
    }
    evidence_list = [_validate_evidence(item, f"evidence[{i}]") for i, item in enumerate(evidence)]
    if not evidence_list:
        raise ReviewValidationError("shadow packet requires bound reviewer evidence")
    if any(item["role"] in NEGATIVE_ROLES and item.get("generationInput") for item in evidence_list):
        raise ReviewValidationError("negative/review-only evidence cannot be a generation input")
    evidence_list = [dict(item, generationInput=False, responsibility="REVIEW_CONTEXT_ONLY") if item["role"] in NEGATIVE_ROLES else item for item in evidence_list]
    policy = _mapping(compiled_policy, "compiledPolicy")
    contract_binding = _record_binding(contract, "contractId", "contract")
    brief_binding = _record_binding(brief, "briefId", "brief")
    policy_binding = {"compiledPolicyId": _required_text(policy, "compiledPolicyId"), "sha256": _sha(policy.get("sha256"), "compiledPolicy.sha256")}
    source_contract_binding = _record_binding(historical_contract or contract, "contractId", "historicalContract")
    policy_record_binding = _record_binding(compiled_policy_record or policy_binding, "compiledPolicyId", "compiledPolicyRecord")
    payload = {
        "schemaVersion": SCHEMA_VERSION, "attemptId": _required_text(attempt, "attemptId"),
        "contract": contract_binding, "brief": brief_binding, "compiledPolicy": policy_binding,
        "reviewContext": {"responsibility": "REVIEW_CONTEXT_ONLY", "contract": contract_binding, "brief": brief_binding,
                          "compiledPolicy": policy_binding, "compiledPolicyRecord": policy_record_binding},
        "historicalProvenance": {"attemptId": _required_text(attempt, "attemptId"), "contract": source_contract_binding,
                                 "artifact": normalized_case["artifact"], "humanDecision": normalized_case["humanDecision"],
                                 "humanFeedback": normalized_case["humanFeedback"]},
        "reviewRound": None, "requiredModel": _text(required_model, "requiredModel"), "reasoningEffort": requested_effort,
        "artifacts": [{"role": "HISTORICAL_CASE_ARTIFACT", **normalized_case["artifact"], "reviewOnly": True, "generationInput": False}], "evidence": evidence_list,
        "acceptanceCases": [{"caseId": normalized_case["caseId"]}], "feedback": [{"feedbackId": normalized_case["humanFeedback"]["feedbackId"]}],
        "frozenInvariants": _unique_text_list(frozen_invariants, "frozenInvariants"),
        "permissions": {"allowedDecisions": list(REVIEW_DECISIONS), "mayApprove": False, "mayMakeHumanDecision": False, "mayUseAggregateAestheticScore": False},
        "qualificationMode": True, "countsTowardFormalAttemptBudget": False, "mayChangeAttemptState": False, "caseBinding": normalized_case,
    }
    packet = {"packetId": stable_id("model-review-packet", payload), **payload}
    packet["sha256"] = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    return validate_model_review_packet(packet)


def validate_model_review_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    packet = deepcopy(dict(_mapping(packet, "packet")))
    common = {"packetId", "sha256", "schemaVersion", "attemptId", "contract", "brief", "compiledPolicy", "reviewRound", "requiredModel", "reasoningEffort", "artifacts", "evidence", "acceptanceCases", "feedback", "frozenInvariants", "permissions"}
    shadow = packet.get("qualificationMode") is True
    shadow_base = {"qualificationMode", "countsTowardFormalAttemptBudget", "mayChangeAttemptState", "caseBinding"}
    shadow_context = {"reviewContext", "historicalProvenance"}
    allowed = common | (shadow_base | shadow_context if shadow else set())
    required = common | (shadow_base if shadow else set())
    _only_keys(packet, allowed, "packet"); _require_keys(packet, required, "packet")
    legacy_shadow = shadow and not any(field in packet for field in shadow_context)
    if shadow and not legacy_shadow and not all(field in packet for field in shadow_context):
        raise ReviewValidationError("shadow packet must bind both review context and historical provenance")
    if packet["schemaVersion"] != SCHEMA_VERSION:
        raise ReviewValidationError("unsupported packet schemaVersion")
    _text(packet["packetId"], "packet.packetId"); _text(packet["attemptId"], "packet.attemptId")
    if shadow:
        if packet["reviewRound"] is not None or packet["reasoningEffort"] not in {"medium", "high", "xhigh"}:
            raise ReviewValidationError("shadow packet requires an explicit formal effort value")
        if packet["countsTowardFormalAttemptBudget"] is not False or packet["mayChangeAttemptState"] is not False:
            raise ReviewValidationError("shadow packet must not consume budget or change attempt state")
        case = _mapping(packet["caseBinding"], "packet.caseBinding")
        _only_keys(case, {"reviewCaseRecord", "caseId", "artifact", "humanDecision", "humanFeedback", "evidenceRegion"}, "packet.caseBinding")
        _require_keys(case, {"reviewCaseRecord", "caseId", "artifact", "humanDecision", "humanFeedback", "evidenceRegion"}, "packet.caseBinding")
        _record_binding(case["reviewCaseRecord"], "reviewCaseRecordId", "packet.caseBinding.reviewCaseRecord")
        _text(case["caseId"], "packet.caseBinding.caseId"); _artifact(case["artifact"], "packet.caseBinding.artifact")
        _text(case["humanDecision"], "packet.caseBinding.humanDecision"); _record_binding(case["humanFeedback"], "feedbackId", "packet.caseBinding.humanFeedback"); _region(case["evidenceRegion"], "packet.caseBinding.evidenceRegion")
        if not legacy_shadow:
            context = _mapping(packet["reviewContext"], "packet.reviewContext")
            _only_keys(context, {"responsibility", "contract", "brief", "compiledPolicy", "compiledPolicyRecord"}, "packet.reviewContext")
            _require_keys(context, {"responsibility", "contract", "brief", "compiledPolicy", "compiledPolicyRecord"}, "packet.reviewContext")
            if context["responsibility"] != "REVIEW_CONTEXT_ONLY":
                raise ReviewValidationError("shadow review context responsibility must be REVIEW_CONTEXT_ONLY")
            if context["contract"] != packet["contract"] or context["brief"] != packet["brief"] or context["compiledPolicy"] != packet["compiledPolicy"]:
                raise ReviewValidationError("shadow review context bindings must match packet rule-evaluation bindings")
            _record_binding(context["compiledPolicyRecord"], "compiledPolicyId", "packet.reviewContext.compiledPolicyRecord")
            provenance = _mapping(packet["historicalProvenance"], "packet.historicalProvenance")
            _only_keys(provenance, {"attemptId", "contract", "artifact", "humanDecision", "humanFeedback"}, "packet.historicalProvenance")
            _require_keys(provenance, {"attemptId", "contract", "artifact", "humanDecision", "humanFeedback"}, "packet.historicalProvenance")
            if provenance["attemptId"] != packet["attemptId"] or provenance["artifact"] != case["artifact"] or provenance["humanDecision"] != case["humanDecision"] or provenance["humanFeedback"] != case["humanFeedback"]:
                raise ReviewValidationError("shadow historical provenance must match the registered case")
            _record_binding(provenance["contract"], "contractId", "packet.historicalProvenance.contract")
    else:
        expected_effort = review_effort(packet["reviewRound"])
        if packet["reasoningEffort"] != expected_effort:
            raise ReviewValidationError("packet reasoning effort does not match review round")
    _text(packet["requiredModel"], "packet.requiredModel")
    _record_binding(packet["contract"], "contractId", "packet.contract"); _record_binding(packet["brief"], "briefId", "packet.brief")
    policy = _mapping(packet["compiledPolicy"], "packet.compiledPolicy"); _required_text(policy, "compiledPolicyId"); _sha(policy.get("sha256"), "packet.compiledPolicy.sha256")
    artifacts = packet["artifacts"]
    if not isinstance(artifacts, list) or not artifacts: raise ReviewValidationError("packet.artifacts must be non-empty")
    roles = []
    for i, artifact in enumerate(artifacts):
        value = _mapping(artifact, f"packet.artifacts[{i}]"); role = _required_text(value, "role"); roles.append(role); _artifact({"path": value.get("path"), "sha256": value.get("sha256")}, f"packet.artifacts[{i}]")
    if len(roles) != len(set(roles)): raise ReviewValidationError("packet artifact roles must be unique")
    if shadow:
        historical_artifacts = [item for item in artifacts if item.get("role") == "HISTORICAL_CASE_ARTIFACT"]
        if len(artifacts) != 1 or len(historical_artifacts) != 1 or historical_artifacts[0].get("path") != case["artifact"].get("path") or historical_artifacts[0].get("sha256") != case["artifact"].get("sha256"):
            raise ReviewValidationError("historical case artifact must match the registered case")
        if not legacy_shadow and (historical_artifacts[0].get("reviewOnly") is not True or historical_artifacts[0].get("generationInput") is not False):
            raise ReviewValidationError("historical case artifacts must remain review-only and forbidden generation input")
        if legacy_shadow and any(key in historical_artifacts[0] for key in ("reviewOnly", "generationInput")):
            raise ReviewValidationError("legacy shadow artifact flags are not part of the immutable packet schema")
    evidence = [_validate_evidence(item, f"packet.evidence[{i}]") for i, item in enumerate(packet["evidence"])]
    if any(item["role"] in NEGATIVE_ROLES and item.get("generationInput") for item in evidence): raise ReviewValidationError("negative/review-only evidence cannot be a generation input")
    for field in ("acceptanceCases", "feedback"):
        if not isinstance(packet[field], list): raise ReviewValidationError(f"packet.{field} must be a list")
    _unique_text_list(packet["frozenInvariants"], "packet.frozenInvariants")
    expected_permissions = {"allowedDecisions": list(REVIEW_DECISIONS), "mayApprove": False, "mayMakeHumanDecision": False, "mayUseAggregateAestheticScore": False}
    if packet["permissions"] != expected_permissions: raise ReviewValidationError("packet permissions exceed Reviewer authority")
    expected_id = stable_id("model-review-packet", {k: v for k, v in packet.items() if k not in {"packetId", "sha256"}})
    if packet["packetId"] != expected_id: raise ReviewValidationError("packetId does not match canonical payload")
    expected_sha = hashlib.sha256(canonical_bytes({k: v for k, v in packet.items() if k != "sha256"})).hexdigest()
    if packet["sha256"] != expected_sha: raise ReviewValidationError("packet sha256 does not match canonical packet")
    return packet


def validate_model_review_result(result: Mapping[str, Any], packet: Mapping[str, Any], compiled_policy: Mapping[str, Any]) -> dict[str, Any]:
    """Strictly validate model output against only packet-bound authority."""
    packet = validate_model_review_packet(packet)
    result = deepcopy(dict(_mapping(result, "result")))
    allowed = {"schemaVersion", "resultId", "packetId", "packetSha256", "decision", "summary", "strengths", "defects", "frozenInvariants", "operations"}
    required = allowed - {"resultId"}
    _only_keys(result, allowed, "result"); _require_keys(result, required, "result")
    if result["schemaVersion"] != SCHEMA_VERSION or result["packetId"] != packet["packetId"] or result["packetSha256"] != packet["sha256"]:
        raise ReviewValidationError("result is not bound to the current packet")
    if result["decision"] not in REVIEW_DECISIONS:
        raise ReviewValidationError("result decision is outside Reviewer authority")
    _text(result["summary"], "result.summary")
    _unique_text_list(result["strengths"], "result.strengths")
    if result["frozenInvariants"] != packet["frozenInvariants"]:
        raise ReviewValidationError("result may not alter frozen invariants")
    policy = _mapping(compiled_policy, "compiledPolicy")
    if policy.get("compiledPolicyId") != packet["compiledPolicy"]["compiledPolicyId"] or policy.get("sha256") != packet["compiledPolicy"]["sha256"]:
        raise ReviewValidationError("compiled policy does not match packet")
    rule_by_id = {r["ruleId"]: r for r in policy.get("rules", [])}
    acceptance_ids = {c.get("caseId") for c in packet["acceptanceCases"] if isinstance(c, Mapping)}
    bound_roles = {a["role"] for a in packet["artifacts"]} | {e["role"] for e in packet["evidence"]}
    defects = result["defects"]
    if not isinstance(defects, list): raise ReviewValidationError("result.defects must be a list")
    defect_ids = set()
    for i, defect in enumerate(defects):
        defect = _mapping(defect, f"result.defects[{i}]")
        _only_keys(defect, {"defectId", "ruleId", "acceptanceCaseId", "severity", "certainty", "observed", "expected", "evidenceRoles", "region"}, f"result.defects[{i}]")
        _require_keys(defect, {"defectId", "ruleId", "acceptanceCaseId", "severity", "certainty", "observed", "expected", "evidenceRoles", "region"}, f"result.defects[{i}]")
        defect_id = _required_text(defect, "defectId"); defect_ids.add(defect_id)
        rule = rule_by_id.get(defect["ruleId"])
        if rule is None: raise ReviewValidationError("defect cites an inactive or unbound rule")
        if defect["acceptanceCaseId"] not in acceptance_ids: raise ReviewValidationError("defect cites an unbound acceptance case")
        if defect["severity"] not in {"hard", "advisory", "human-only"} or defect["severity"] != rule["authority"]:
            raise ReviewValidationError("defect severity exceeds or disagrees with rule authority")
        if defect["certainty"] not in {"certain", "uncertain"}: raise ReviewValidationError("defect certainty is invalid")
        _text(defect["observed"], "defect.observed"); _text(defect["expected"], "defect.expected")
        cited = set(_unique_text_list(defect["evidenceRoles"], "defect.evidenceRoles", nonempty=True))
        if not cited <= bound_roles: raise ReviewValidationError("defect cites evidence outside the packet")
        _region(defect["region"], "defect.region")
    packet_anchor_roles = {
        item["role"] for item in [*packet["artifacts"], *packet["evidence"]]
        if item["role"] in GENERATION_INPUT_ROLES and item.get("generationInput") is not False
    }
    operations = validate_controlled_operations(
        result["operations"], frozen_invariants=packet["frozenInvariants"], defect_ids=defect_ids,
        bound_anchor_roles=packet_anchor_roles,
    )
    if result["decision"] == "retry" and not defects:
        raise ReviewValidationError("retry requires at least one defect")
    if result["decision"] != "retry" and operations:
        raise ReviewValidationError("only retry may contain controlled operations")
    payload = {k: v for k, v in result.items() if k != "resultId"}; payload["operations"] = operations
    expected_id = stable_id("model-review-result", payload)
    if result.get("resultId") not in {None, expected_id}:
        raise ReviewValidationError("resultId does not match canonical result")
    return {"resultId": expected_id, **payload}


def validate_controlled_operations(
    operations: Sequence[Mapping[str, Any]], *, frozen_invariants: Sequence[str], defect_ids: Iterable[str],
    bound_anchor_roles: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(operations, list): raise ReviewValidationError("operations must be a list")
    frozen = set(_unique_text_list(frozen_invariants, "frozenInvariants")); defects = set(defect_ids)
    packet_anchors = None if bound_anchor_roles is None else set(_unique_text_list(list(bound_anchor_roles), "boundAnchorRoles"))
    result = []
    for i, operation in enumerate(operations):
        value = deepcopy(dict(_mapping(operation, f"operations[{i}]")))
        _only_keys(value, {"operation", "target", "instruction", "defectId", "anchorRole"}, f"operations[{i}]")
        _require_keys(value, {"operation", "target", "instruction", "defectId"}, f"operations[{i}]")
        if value["operation"] not in CONTROLLED_OPERATIONS: raise ReviewValidationError("uncontrolled operation")
        target = _text(value["target"], "operation.target")
        _text(value["instruction"], "operation.instruction")
        if value["defectId"] not in defects: raise ReviewValidationError("operation is not bound to a reported defect")
        if target in frozen and value["operation"] != "preserve": raise ReviewValidationError("operation would change a frozen invariant")
        if value["operation"] == "restore_from_anchor" and value.get("anchorRole") not in GENERATION_INPUT_ROLES:
            raise ReviewValidationError("restore_from_anchor requires an approved positive anchor role")
        if value["operation"] == "restore_from_anchor" and packet_anchors is not None and value["anchorRole"] not in packet_anchors:
            raise ReviewValidationError("restore_from_anchor anchorRole is not bound to the review packet")
        if value["operation"] != "restore_from_anchor" and "anchorRole" in value:
            raise ReviewValidationError("anchorRole is only valid for restore_from_anchor")
        result.append(value)
    return result


def compile_controlled_operations(operations: Sequence[Mapping[str, Any]], *, frozen_invariants: Sequence[str], defect_ids: Iterable[str]) -> dict[str, Any]:
    values = validate_controlled_operations(list(operations), frozen_invariants=frozen_invariants, defect_ids=defect_ids)
    order = {name: index for index, name in enumerate(CONTROLLED_OPERATIONS)}
    values.sort(key=lambda item: (order[item["operation"]], item["target"], item["defectId"], item["instruction"]))
    lines = [f"{item['operation'].upper()} {item['target']}: {item['instruction']}" + (f" FROM {item['anchorRole']}" if item.get("anchorRole") else "") for item in values]
    payload = {"operations": values, "promptDelta": lines}
    return {"promptDeltaId": stable_id("review-prompt-delta", payload), **payload}


def qualification_matches(qualification: Mapping[str, Any], *, authority: ReviewAuthority, rule: Mapping[str, Any], model: str, effort: str, reviewer_prompt_id: str, reviewer_prompt_sha256: str, compiled_policy: Mapping[str, Any], case_set_version: str) -> bool:
    """Return whether a structurally valid, identity-bearing qualification matches this invocation."""
    try:
        qualification = _mapping(qualification, "qualification"); rule = _mapping(rule, "rule"); policy = _mapping(compiled_policy, "compiledPolicy")
        qualification_id = _required_text(qualification, "reviewerQualificationId")
        identity_payload = {key: value for key, value in qualification.items()
                            if key not in {"schemaVersion", "reviewerQualificationId"}}
        if qualification_id != stable_id("reviewer-qualification", identity_payload):
            raise ReviewValidationError("qualification identity does not match its canonical payload")
        state = _required_text(qualification, "state")
        if state not in QUALIFICATION_STATES:
            raise ReviewValidationError("qualification.state is invalid")
        _required_text(qualification, "reviewer")
        _required_text(qualification, "ruleId"); _positive_int(qualification.get("ruleVersion"), "qualification.ruleVersion")
        _required_text(qualification, "model"); qualification_effort = _required_text(qualification, "effort")
        if qualification_effort not in {"medium", "high", "xhigh"}:
            raise ReviewValidationError("qualification.effort is invalid")
        _required_text(qualification, "reviewerPromptId"); _sha(qualification.get("reviewerPromptSha256"), "qualification.reviewerPromptSha256")
        _required_text(qualification, "compiledPolicyId"); _sha(qualification.get("compiledPolicySha256"), "qualification.compiledPolicySha256")
        _required_text(qualification, "caseSetVersion")
        comparison = _mapping(qualification.get("promptOnlyComparison"), "qualification.promptOnlyComparison")
        _required_text(comparison, "promptComparisonId")
    except ReviewValidationError:
        return False
    return bool(
        state == "auto-retry-qualified"
        and qualification["reviewer"] == authority.reviewer
        and qualification["ruleId"] == rule.get("ruleId")
        and qualification["ruleVersion"] == rule.get("version")
        and qualification["model"] == model and qualification["effort"] == effort
        and qualification["reviewerPromptId"] == reviewer_prompt_id
        and qualification["reviewerPromptSha256"] == reviewer_prompt_sha256
        and qualification["compiledPolicyId"] == policy.get("compiledPolicyId")
        and qualification["compiledPolicySha256"] == policy.get("sha256")
        and qualification["caseSetVersion"] == case_set_version
        and not qualification.get("suspendedAt") and not qualification.get("supersededBy")
    )


def evaluate_automatic_decision(result: Mapping[str, Any], *, authority: ReviewAuthority, packet: Mapping[str, Any], compiled_policy: Mapping[str, Any], qualifications: Sequence[Mapping[str, Any]], model: str, reviewer_prompt_id: str, reviewer_prompt_sha256: str, case_set_version: str) -> dict[str, Any]:
    model = _text(model, "model"); reviewer_prompt_id = _text(reviewer_prompt_id, "reviewerPromptId")
    reviewer_prompt_sha256 = _sha(reviewer_prompt_sha256, "reviewerPromptSha256")
    case_set_version = _text(case_set_version, "caseSetVersion")
    result = validate_model_review_result(result, packet, compiled_policy)
    round_number = packet["reviewRound"]
    if result["decision"] == "pass_to_human": return {"action": "review_pending", "automaticRetry": False, "reason": "reviewer_passed_to_human"}
    if result["decision"] == "escalate_to_human": return {"action": "human_review_required", "automaticRetry": False, "reason": "reviewer_escalated"}
    if round_number >= 3: return {"action": "human_review_required", "automaticRetry": False, "reason": "automatic_generation_budget_exhausted"}
    rules = {r["ruleId"]: r for r in compiled_policy.get("rules", [])}
    qualification_ids = set()
    for defect in result["defects"]:
        rule = rules[defect["ruleId"]]
        if defect["severity"] != "hard" or defect["certainty"] != "certain" or not rule.get("autoRetryEligible"):
            return {"action": "human_review_required", "automaticRetry": False, "reason": "defect_not_auto_retry_eligible", "ruleId": defect["ruleId"]}
        if not set(rule.get("requiredEvidenceRoles", [])) <= set(defect["evidenceRoles"]):
            return {"action": "human_review_required", "automaticRetry": False, "reason": "required_evidence_incomplete", "ruleId": defect["ruleId"]}
        matches = [qualification for qualification in qualifications
                   if qualification_matches(qualification, authority=authority, rule=rule, model=model, effort=packet["reasoningEffort"],
                                            reviewer_prompt_id=reviewer_prompt_id, reviewer_prompt_sha256=reviewer_prompt_sha256,
                                            compiled_policy=compiled_policy, case_set_version=case_set_version)]
        if not matches:
            return {"action": "human_review_required", "automaticRetry": False, "reason": "rule_not_qualified_for_invocation", "ruleId": defect["ruleId"]}
        matches_by_id: dict[str, Mapping[str, Any]] = {}
        for match in matches:
            qualification_id = match["reviewerQualificationId"]
            if qualification_id in matches_by_id and match != matches_by_id[qualification_id]:
                return {"action": "human_review_required", "automaticRetry": False, "reason": "conflicting_qualification_identity", "ruleId": defect["ruleId"]}
            matches_by_id[qualification_id] = match
        qualification_ids.add(sorted(matches_by_id)[-1])
    compiled = compile_controlled_operations(result["operations"], frozen_invariants=packet["frozenInvariants"], defect_ids={d["defectId"] for d in result["defects"]})
    return {"action": "automatic_retry", "automaticRetry": True, "nextRound": round_number + 1,
            "nextEffort": review_effort(round_number + 1), "qualificationIds": sorted(qualification_ids),
            "promptDelta": compiled}


def validate_experience_candidate(candidate: Mapping[str, Any], *, authority: ReviewAuthority) -> dict[str, Any]:
    candidate = deepcopy(dict(_mapping(candidate, "candidate")))
    allowed = {"schemaVersion", "lessonCandidateId", "feedbackId", "attemptId", "action", "targetRuleId", "proposedScope", "caseDraft", "ruleDraft", "rationale", "status", "createdBy", "promoted", "promotedBy"}
    _only_keys(candidate, allowed, "candidate")
    _require_keys(candidate, {"feedbackId", "attemptId", "action", "rationale", "status", "createdBy"}, "candidate")
    _text(candidate["feedbackId"], "candidate.feedbackId"); _text(candidate["attemptId"], "candidate.attemptId")
    if candidate["action"] not in EXPERIENCE_ACTIONS: raise ReviewValidationError("candidate.action is invalid")
    _text(candidate["rationale"], "candidate.rationale")
    if candidate["status"] not in {"proposed", "rejected", "promoted"}: raise ReviewValidationError("candidate.status is invalid")
    if candidate["createdBy"] == authority.reviewer: raise ReviewValidationError("lesson candidate must identify the curator, not impersonate the authority reviewer")
    if candidate.get("promoted") is True or candidate["status"] == "promoted" or candidate.get("promotedBy") is not None:
        raise ReviewValidationError("lesson candidates cannot self-promote policy")
    if candidate["action"] in {"narrow-scope", "scoped-exception"}:
        _required_text(candidate, "targetRuleId"); _validate_scope(candidate.get("proposedScope"), "candidate.proposedScope")
    elif candidate["action"] == "add-case":
        _required_text(candidate, "targetRuleId"); _mapping(candidate.get("caseDraft"), "candidate.caseDraft")
    elif candidate["action"] == "draft-rule":
        draft = _mapping(candidate.get("ruleDraft"), "candidate.ruleDraft")
        if draft.get("lifecycle") not in {None, "draft"} or draft.get("autoRetryEligible") is True:
            raise ReviewValidationError("new lesson rules must start draft and unqualified")
    payload = {k: v for k, v in candidate.items() if k not in {"lessonCandidateId", "schemaVersion"}}
    expected = stable_id("review-lesson-candidate", payload)
    if candidate.get("lessonCandidateId") not in {None, expected}: raise ReviewValidationError("lessonCandidateId does not match canonical candidate")
    return {"schemaVersion": SCHEMA_VERSION, "lessonCandidateId": expected, **payload}


def validate_prompt_only_comparison_arm(arm: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one immutable, raw-count-only arm of a prompt comparison."""
    arm = deepcopy(dict(_mapping(arm, "promptComparisonArm")))
    allowed = {"schemaVersion", "arm", "contract", "anchors", "context", "imageGenBudget", "rawCounts"}
    _only_keys(arm, allowed, "promptComparisonArm"); _require_keys(arm, allowed - {"schemaVersion"}, "promptComparisonArm")
    if arm.get("schemaVersion", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ReviewValidationError("unsupported prompt comparison arm schemaVersion")
    if arm["arm"] not in {"prompt-only", "reviewer-closed-loop"}:
        raise ReviewValidationError("prompt comparison arm is invalid")
    _record_binding(arm["contract"], "contractId", "promptComparisonArm.contract")
    anchors = arm["anchors"]
    if not isinstance(anchors, list) or not anchors:
        raise ReviewValidationError("prompt comparison anchors must be non-empty")
    normalized_anchors = [_artifact(item, f"promptComparisonArm.anchors[{index}]") for index, item in enumerate(anchors)]
    if len({(item["path"], item["sha256"]) for item in normalized_anchors}) != len(normalized_anchors):
        raise ReviewValidationError("prompt comparison anchors must be unique")
    context = deepcopy(dict(_mapping(arm["context"], "promptComparisonArm.context")))
    if not context:
        raise ReviewValidationError("prompt comparison context must be non-empty")
    budget = _positive_int(arm["imageGenBudget"], "promptComparisonArm.imageGenBudget")
    raw_counts = arm["rawCounts"]
    if not isinstance(raw_counts, list) or not raw_counts:
        raise ReviewValidationError("prompt comparison rawCounts must be non-empty")
    count_keys = {"knownHardErrorsReachedHuman", "repeatedHardErrors", "reviewerMisses", "falsePositives", "repeatedHumanFeedback", "imageGenRounds", "escalations"}
    normalized_counts = []
    seen = set()
    for index, row in enumerate(raw_counts):
        row = deepcopy(dict(_mapping(row, f"promptComparisonArm.rawCounts[{index}]")))
        _only_keys(row, {"ruleId", "context", *count_keys}, f"promptComparisonArm.rawCounts[{index}]")
        _require_keys(row, {"ruleId", "context", *count_keys}, f"promptComparisonArm.rawCounts[{index}]")
        rule_id = _required_text(row, "ruleId")
        row_context = deepcopy(dict(_mapping(row["context"], f"promptComparisonArm.rawCounts[{index}].context")))
        if not row_context:
            raise ReviewValidationError("prompt comparison raw count context must be non-empty")
        key = (rule_id, json.dumps(row_context, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        if key in seen:
            raise ReviewValidationError("prompt comparison raw counts must be unique per rule and context")
        seen.add(key)
        for count_key in count_keys:
            value = row[count_key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ReviewValidationError(f"prompt comparison {count_key} must be a non-negative integer")
        normalized_counts.append({"ruleId": rule_id, "context": row_context, **{key: row[key] for key in sorted(count_keys)}})
    return {"schemaVersion": SCHEMA_VERSION, "arm": arm["arm"], "contract": _record_binding(arm["contract"], "contractId", "promptComparisonArm.contract"),
            "anchors": sorted(normalized_anchors, key=lambda item: (item["path"], item["sha256"])), "context": context,
            "imageGenBudget": budget, "rawCounts": sorted(normalized_counts, key=lambda item: (item["ruleId"], json.dumps(item["context"], ensure_ascii=False, sort_keys=True)))}


def validate_prompt_only_comparison(prompt_only_arm: Mapping[str, Any], reviewer_arm: Mapping[str, Any]) -> dict[str, Any]:
    """Bind exactly comparable prompt-only and Reviewer closed-loop raw counts."""
    prompt_only = validate_prompt_only_comparison_arm(prompt_only_arm)
    reviewer = validate_prompt_only_comparison_arm(reviewer_arm)
    if prompt_only["arm"] != "prompt-only" or reviewer["arm"] != "reviewer-closed-loop":
        raise ReviewValidationError("prompt comparison requires prompt-only and reviewer-closed-loop arms")
    for key in ("contract", "anchors", "context", "imageGenBudget"):
        if prompt_only[key] != reviewer[key]:
            raise ReviewValidationError(f"prompt comparison arms have mismatched {key}")
    payload = {"promptOnly": prompt_only, "reviewerClosedLoop": reviewer}
    return {"schemaVersion": SCHEMA_VERSION, "promptComparisonId": stable_id("prompt-only-comparison", payload), **payload}


# Compatibility-oriented explicit aliases for later CLI adapters.
derive_history_index_entry = derive_review_history_index_entry
case_fitness_audit = audit_case_fitness
compile_policy = compile_review_policy
validate_model_review_packet_payload = validate_model_review_packet
validate_model_review_result_payload = validate_model_review_result
evaluate_automatic_review_decision = evaluate_automatic_decision


def _assert_json_value(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, int, bool)): return
    if isinstance(value, float):
        if not math.isfinite(value): raise ReviewValidationError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for i, item in enumerate(value): _assert_json_value(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str): raise ReviewValidationError(f"{path} contains a non-string JSON key")
            _assert_json_value(item, f"{path}.{key}")
        return
    raise ReviewValidationError(f"{path} is not JSON-serializable")


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ReviewValidationError(f"{path} must be an object")
    _assert_json_value(dict(value), path); return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip(): raise ReviewValidationError(f"{path} must be non-empty text")
    return value


def _required_text(value: Mapping[str, Any], key: str) -> str: return _text(value.get(key), key)


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1: raise ReviewValidationError(f"{path} must be a positive integer")
    return value


def _sha(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value): raise ReviewValidationError(f"{path} must be a lowercase SHA-256")
    return value


def _artifact(value: Any, path: str) -> dict[str, str]:
    value = _mapping(value, path); _only_keys(value, {"path", "sha256"}, path)
    artifact_path = _required_text(value, "path")
    parts = artifact_path.split("/")
    if ("\\" in artifact_path or artifact_path.startswith("/")
            or re.match(r"^[A-Za-z]:", artifact_path)
            or any(part in {"", ".", ".."} for part in parts)):
        raise ReviewValidationError(f"{path}.path must be a repository-relative POSIX path")
    return {"path": artifact_path, "sha256": _sha(value.get("sha256"), f"{path}.sha256")}


def _record_binding(value: Any, id_field: str, path: str) -> dict[str, str]:
    value = _mapping(value, path); return {id_field: _required_text(value, id_field), "sha256": _sha(value.get("sha256"), f"{path}.sha256")}


def _unique_text_list(value: Any, path: str, nonempty: bool = False) -> list[str]:
    if not isinstance(value, (list, tuple)) or isinstance(value, str): raise ReviewValidationError(f"{path} must be a list")
    result = [_text(item, f"{path}[]") for item in value]
    if nonempty and not result: raise ReviewValidationError(f"{path} must not be empty")
    if len(result) != len(set(result)): raise ReviewValidationError(f"{path} must not contain duplicates")
    return result


def _validate_scope(value: Any, path: str) -> Mapping[str, Any]:
    value = _mapping(value, path); _only_keys(value, set(SCOPE_FIELDS), path)
    for field, expected in value.items():
        if isinstance(expected, list): _unique_text_list(expected, f"{path}.{field}", nonempty=True)
        else: _text(expected, f"{path}.{field}")
    return value


def _scope_specificity(scope: Mapping[str, Any]) -> int: return sum(1 for value in scope.values() if value != "*" and value != ["*"])


def _validate_evidence(value: Any, path: str) -> dict[str, Any]:
    value = deepcopy(dict(_mapping(value, path)))
    _only_keys(value, {"role", "path", "sha256", "generationInput", "caseId", "responsibility"}, path)
    role = _required_text(value, "role")
    if not _EVIDENCE_ROLE_RE.fullmatch(role): raise ReviewValidationError(f"{path}.role is invalid")
    artifact = _artifact({"path": value.get("path"), "sha256": value.get("sha256")}, path)
    if "generationInput" in value and not isinstance(value["generationInput"], bool): raise ReviewValidationError(f"{path}.generationInput must be boolean")
    return {"role": role, **artifact, **{k: value[k] for k in ("generationInput", "caseId", "responsibility") if k in value}}


def _region(value: Any, path: str) -> dict[str, float]:
    value = _mapping(value, path); _only_keys(value, {"x", "y", "width", "height"}, path); _require_keys(value, {"x", "y", "width", "height"}, path)
    result = {}
    for key in ("x", "y", "width", "height"):
        number = value[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)): raise ReviewValidationError(f"{path}.{key} must be numeric")
        if number < 0 or number > 1 or key in {"width", "height"} and number == 0: raise ReviewValidationError(f"{path} must be normalized within 0..1")
        result[key] = number
    if result["x"] + result["width"] > 1 or result["y"] + result["height"] > 1: raise ReviewValidationError(f"{path} exceeds normalized image bounds")
    return result


def _only_keys(value: Mapping[str, Any], allowed: set[str], path: str) -> None:
    unknown = set(value) - allowed
    if unknown: raise ReviewValidationError(f"{path} contains unknown fields: {sorted(unknown)}")


def _require_keys(value: Mapping[str, Any], required: set[str], path: str) -> None:
    missing = required - set(value)
    if missing: raise ReviewValidationError(f"{path} is missing fields: {sorted(missing)}")
