from __future__ import annotations

import pytest

from maliang_art import review, stable_id

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


def model_packet(*, include_identity_anchor=False, identity_generation_input=True):
    evidence = [{"role": "CALIBRATED_MASTER", "path": "evidence/master.png", "sha256": SHA, "generationInput": True}]
    if include_identity_anchor:
        evidence.append({"role": "POSITIVE_IDENTITY_ANCHOR", "path": "evidence/identity.png", "sha256": SHA, "generationInput": identity_generation_input})
    return review.build_model_review_packet(
        attempt={"attemptId": "demo-a001"},
        contract={"contractId": "contract-one", "sha256": SHA},
        brief={"briefId": "brief-one", "sha256": SHA},
        compiled_policy=compiled_policy(),
        artifacts={"candidate": {"path": "attempts/demo.png", "sha256": SHA}},
        evidence=evidence,
        acceptance_cases=[{"caseId": "case-one"}], feedback=[], frozen_invariants=["identity"],
        required_model="review-model",
    )


def retry_result(packet, *, operation="adjust"):
    controlled = {"operation": operation, "target": "arm", "instruction": "move outward", "defectId": "d1"}
    if operation == "restore_from_anchor":
        controlled["anchorRole"] = "POSITIVE_IDENTITY_ANCHOR"
    return {
        "schemaVersion": 1, "packetId": packet["packetId"], "packetSha256": packet["sha256"],
        "decision": "retry", "summary": "Hard silhouette defect", "strengths": [],
        "defects": [{"defectId": "d1", "ruleId": "silhouette", "acceptanceCaseId": "case-one",
                     "severity": "hard", "certainty": "certain", "observed": "arm is inward",
                     "expected": "arm is outward", "evidenceRoles": ["CALIBRATED_MASTER"],
                     "region": {"x": 0, "y": 0, "width": 1, "height": 1}}],
        "frozenInvariants": ["identity"], "operations": [controlled],
    }


def qualification(**changes):
    policy = compiled_policy()
    value = {
        "state": "auto-retry-qualified",
        "reviewer": AUTHORITY.reviewer, "ruleId": "silhouette", "ruleVersion": 1,
        "model": "review-model", "effort": "medium", "reviewerPromptId": "prompt-one",
        "reviewerPromptSha256": SHA, "compiledPolicyId": policy["compiledPolicyId"],
        "compiledPolicySha256": policy["sha256"], "caseSetVersion": "cases-v1",
        "promptOnlyComparison": {"promptComparisonId": "comparison-one"},
    }
    identity_override = changes.pop("reviewerQualificationId", None)
    value.update(changes)
    value["reviewerQualificationId"] = stable_id("reviewer-qualification", value)
    if identity_override is not None:
        value["reviewerQualificationId"] = identity_override
    return value


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
    assert first == second
    assert first["compiledPolicyId"] == "compiled-review-policy-129d517633260989"
    assert first["sha256"] == "129d517633260989407d00437fd25df430888ffb199131343fa65f7f2f4f85f8"
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


@pytest.mark.parametrize("decision", ["rejected", "retry", "superseded"])
def test_rejected_evidence_cannot_be_relabelled_as_positive_input(decision):
    with pytest.raises(review.ReviewValidationError, match="approving human decision"):
        review.validate_review_case(case(source={"attemptId": "demo-a001", "humanDecision": decision, "reviewer": AUTHORITY.reviewer}), authority=AUTHORITY)


def test_approved_evidence_cannot_be_relabelled_as_negative():
    with pytest.raises(review.ReviewValidationError, match="rejecting human decision"):
        review.validate_review_case(case(polarity="negative", reviewOnly=True, generationInputAllowed=False), authority=AUTHORITY)


def test_only_positive_non_review_cases_can_be_generation_inputs():
    with pytest.raises(review.ReviewValidationError, match="only positive"):
        review.validate_review_case(case(polarity="boundary", generationInputAllowed=True), authority=AUTHORITY)
    with pytest.raises(review.ReviewValidationError, match="non-review-only"):
        review.validate_review_case(case(reviewOnly=True, generationInputAllowed=True), authority=AUTHORITY)


def test_boundary_case_requires_a_known_human_decision():
    with pytest.raises(review.ReviewValidationError, match="humanDecision is invalid"):
        review.validate_review_case(case(polarity="boundary", source={"attemptId": "demo-a001", "humanDecision": "maybe", "reviewer": AUTHORITY.reviewer}, generationInputAllowed=False), authority=AUTHORITY)


def test_restore_from_anchor_role_must_be_bound_to_packet():
    packet = model_packet()
    with pytest.raises(review.ReviewValidationError, match="not bound to the review packet"):
        review.validate_model_review_result(retry_result(packet, operation="restore_from_anchor"), packet, compiled_policy())

    review_only_anchor_packet = model_packet(include_identity_anchor=True, identity_generation_input=False)
    with pytest.raises(review.ReviewValidationError, match="not bound to the review packet"):
        review.validate_model_review_result(retry_result(review_only_anchor_packet, operation="restore_from_anchor"), review_only_anchor_packet, compiled_policy())

    bound_packet = model_packet(include_identity_anchor=True)
    validated = review.validate_model_review_result(retry_result(bound_packet, operation="restore_from_anchor"), bound_packet, compiled_policy())
    assert validated["operations"][0]["anchorRole"] == "POSITIVE_IDENTITY_ANCHOR"


def test_automatic_retry_requires_identity_bearing_qualification():
    packet = model_packet()
    result = retry_result(packet)
    invocation = {
        "authority": AUTHORITY, "packet": packet, "compiled_policy": compiled_policy(),
        "model": "review-model", "reviewer_prompt_id": "prompt-one",
        "reviewer_prompt_sha256": SHA, "case_set_version": "cases-v1",
    }
    missing_identity = qualification()
    del missing_identity["reviewerQualificationId"]
    denied = review.evaluate_automatic_decision(result, qualifications=[missing_identity], **invocation)
    assert denied == {"action": "human_review_required", "automaticRetry": False,
                      "reason": "rule_not_qualified_for_invocation", "ruleId": "silhouette"}

    allowed = review.evaluate_automatic_decision(result, qualifications=[qualification()], **invocation)
    assert allowed["automaticRetry"] is True
    assert allowed["qualificationIds"] == [qualification()["reviewerQualificationId"]]

    tampered = qualification()
    tampered["unsignedNote"] = "changed after qualification"
    denied = review.evaluate_automatic_decision(result, qualifications=[tampered], **invocation)
    assert denied["reason"] == "rule_not_qualified_for_invocation"


@pytest.mark.parametrize("changes", [
    {"reviewerQualificationId": 7},
    {"ruleVersion": True},
    {"promptOnlyComparison": {"promptComparisonId": 9}},
    {"reviewerPromptSha256": "not-a-sha"},
])
def test_malformed_qualification_bindings_fail_closed(changes):
    packet = model_packet()
    decision = review.evaluate_automatic_decision(
        retry_result(packet), authority=AUTHORITY, packet=packet, compiled_policy=compiled_policy(),
        qualifications=[qualification(**changes)], model="review-model", reviewer_prompt_id="prompt-one",
        reviewer_prompt_sha256=SHA, case_set_version="cases-v1",
    )
    assert decision["automaticRetry"] is False
    assert decision["reason"] == "rule_not_qualified_for_invocation"


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_rejects_non_finite_numbers(number):
    with pytest.raises(review.ReviewValidationError, match="non-finite"):
        review.canonical_bytes({"nested": [number]})


def test_canonical_json_bytes_for_finite_fixture_are_unchanged():
    assert review.canonical_bytes({"finite": 1.5, "ok": True}) == b'{"finite":1.5,"ok":true}\n'
