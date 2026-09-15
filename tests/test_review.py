from __future__ import annotations

import pytest

from maliang_art import review

SHA = "b" * 64
AUTHORITY = review.ReviewAuthority("art-director")


def rule(**changes):
    value = {"schemaVersion": 1, "ruleId": "silhouette", "version": 1, "scope": {"project": "demo"}, "authority": "hard", "autoRetryEligible": True, "requiredEvidenceRoles": ["CALIBRATED_MASTER"], "sources": [{"type": "guide", "id": "g1"}], "positiveCaseIds": [], "negativeCaseIds": [], "lifecycle": "active", "statement": "Synthetic silhouette must be readable"}
    value.update(changes); return value


def case(**changes):
    value = {"schemaVersion": 1, "caseId": "case-one", "version": 1, "ruleIds": ["silhouette"], "polarity": "positive", "status": "active", "scope": {"project": "demo"}, "artifact": {"path": "examples/synthetic.png", "sha256": SHA}, "source": {"attemptId": "demo-a001", "humanDecision": "approved", "reviewer": "art-director"}, "reviewOnly": False, "generationInputAllowed": True}
    value.update(changes); return value


def compiled_policy():
    return review.compile_review_policy({"policyId": "demo-policy", "version": 1}, [rule()], [case()], {"project": "demo"}, authority=AUTHORITY, acceptance_case_ids=["case-one"])


def test_review_rule_and_case_validate():
    assert review.validate_review_rule(rule())["ruleId"] == "silhouette"
    assert review.validate_review_case(case(), authority=AUTHORITY)["caseId"] == "case-one"


def test_review_authority_is_explicit_and_configurable():
    with pytest.raises(review.ReviewValidationError):
        review.ReviewAuthority("")
    with pytest.raises(review.ReviewValidationError):
        review.validate_review_case(case(source={"attemptId": "demo-a001", "humanDecision": "approved", "reviewer": "other"}), authority=AUTHORITY)


def test_non_hard_rule_cannot_auto_retry():
    with pytest.raises(review.ReviewValidationError): review.validate_review_rule(rule(authority="advisory"))


def test_negative_case_cannot_be_generation_input():
    with pytest.raises(review.ReviewValidationError): review.validate_review_case(case(polarity="negative", reviewOnly=True, generationInputAllowed=True), authority=AUTHORITY)


def test_policy_compile_is_deterministic_and_scope_bound():
    first = compiled_policy(); second = compiled_policy()
    assert first == second and len(first["sha256"]) == 64
    with pytest.raises(review.ReviewValidationError):
        review.compile_review_policy({"policyId": "p", "version": 1}, [rule()], [case()], {"project": "other"}, authority=AUTHORITY, acceptance_case_ids=["case-one"])

@pytest.mark.parametrize("round_number,effort", [(1, "medium"), (2, "high"), (3, "xhigh"), ("demo-a002", "high")])
def test_review_effort(round_number, effort):
    assert review.review_effort(round_number) == effort

@pytest.mark.parametrize("bad", [0, 4, True, "a2"])
def test_review_effort_rejects_bad_rounds(bad):
    with pytest.raises(review.ReviewValidationError): review.review_effort(bad)


def test_controlled_operations_are_sorted_and_bound():
    operations = [
        {"operation": "adjust", "target": "arm", "instruction": "move outward", "defectId": "d2"},
        {"operation": "remove", "target": "noise", "instruction": "remove speck", "defectId": "d1"},
    ]
    compiled = review.compile_controlled_operations(operations, frozen_invariants=["identity"], defect_ids={"d1", "d2"})
    assert [row["operation"] for row in compiled["operations"]] == ["remove", "adjust"]


def test_controlled_operation_cannot_change_frozen_invariant():
    with pytest.raises(review.ReviewValidationError):
        review.validate_controlled_operations([{"operation": "adjust", "target": "identity", "instruction": "change", "defectId": "d1"}], frozen_invariants=["identity"], defect_ids={"d1"})


def test_history_entry_is_stable():
    feedback = {"feedbackId": "f1", "attemptId": "demo-a001", "categories": ["shape"], "disposition": "retry"}
    assert review.derive_history_index_entry(feedback) == review.derive_history_index_entry(feedback)


def test_case_fitness_rejects_non_authoritative_source():
    candidate = {"polarity": "positive", "source": {"attemptId": "a", "humanDecision": "approved", "reviewer": "someone"}, "artifact": {"path": "x", "sha256": SHA}, "scope": {"project": "demo"}, "observableAtReviewSize": True, "artifactExists": True, "hashVerified": True, "defectIds": []}
    result = review.audit_case_fitness(candidate, authority=AUTHORITY)
    assert result["status"] == "invalid" and "non_authoritative_human_source" in result["reasons"]


def test_experience_candidate_cannot_impersonate_authority():
    with pytest.raises(review.ReviewValidationError):
        review.validate_experience_candidate({"feedbackId": "f", "attemptId": "a", "action": "reject-learning", "rationale": "none", "status": "proposed", "createdBy": AUTHORITY.reviewer}, authority=AUTHORITY)
