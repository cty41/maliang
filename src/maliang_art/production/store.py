"""Immutable production events and a replaceable current-candidate projection."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from uuid import uuid4

from ..core import (
    CollisionError, MaLiangError, _assert_plain_path, canonical_bytes,
    contained_path, read_contained_bytes, stable_id, write_immutable_bytes,
    write_immutable_json,
)
from ..records import validate_artifact
from ..workflow import validate_delivery, validate_failure, validate_invocation


_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_EVENT = re.compile(r"production-event-[0-9a-f]{64}")
_CANDIDATES = {"generation", "edit", "imported", "historical", "derived"}


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MaLiangError(f"{name} must be non-empty text")
    return value


def _token(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise MaLiangError(f"{name} must be a portable identifier")
    return value


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MaLiangError(f"{name} must be a JSON object")
    canonical_bytes(value)
    return deepcopy(value)


def _checklist(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise MaLiangError("identity_checklist must contain required identity items")
    items = [_text(item, "identity item") for item in value]
    if len(set(items)) != len(items):
        raise MaLiangError("identity_checklist contains duplicate items")
    return items


def _manifest(value: Any, identity_checklist: list[str]) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise MaLiangError("required_acceptance must contain required acceptance items")
    items = []
    methods = {}
    for item in value:
        item = _object(item, "acceptance item")
        if set(item) != {"id", "method"}:
            raise MaLiangError("acceptance item requires id and method")
        item_id = _text(item["id"], "acceptance id")
        if not isinstance(item["method"], str) or item["method"] not in {"human", "automatic"}:
            raise MaLiangError("acceptance method must be human or automatic")
        if item_id in methods:
            raise MaLiangError("duplicate acceptance id")
        methods[item_id] = item["method"]
        items.append(item)
    if any(methods.get(item) != "human" for item in identity_checklist):
        raise MaLiangError("every identity item must require human acceptance")
    return items


class ProductionStore:
    """A narrow on-disk record API, not a provider executor or human authenticator.

    A project adapter must persist a prepared request before executing exactly its
    invocation request. Human decisions are explicit caller attestations backed
    by evidence, not permissions or conclusions inferred by this library.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _read(self, relative: str) -> dict[str, Any]:
        try:
            value = json.loads(read_contained_bytes(self.root, relative))
        except (OSError, ValueError) as exc:
            raise MaLiangError(f"cannot read production record: {relative}") from exc
        return _object(value, "production record")

    def _event(self, record_type: str, **payload: Any) -> dict[str, Any]:
        value = {"schemaVersion": 1, "recordType": record_type, **deepcopy(payload)}
        value["eventId"] = stable_id("production-event", value, length=64)
        write_immutable_json(self.root, f"production/events/{value['eventId']}.json", value)
        return value

    def _require(self, value: Any) -> dict[str, Any]:
        value = _object(value, "event")
        event_id = value.get("eventId")
        if not isinstance(event_id, str) or not _EVENT.fullmatch(event_id):
            raise MaLiangError("invalid production eventId")
        payload = {key: item for key, item in value.items() if key != "eventId"}
        if type(value.get("schemaVersion")) is not int or value["schemaVersion"] != 1 or stable_id("production-event", payload, length=64) != event_id:
            raise MaLiangError("event identity does not match payload")
        if self._read(f"production/events/{event_id}.json") != value:
            raise MaLiangError("event differs from immutable source event")
        for field in ("artifact", "evidence"):
            if field in value:
                validate_artifact(value[field], root=self.root, verify=True)
        return value

    def _candidate(self, value: Any) -> dict[str, Any]:
        value = self._require(value)
        if value["recordType"] not in _CANDIDATES:
            raise MaLiangError("event is not a candidate")
        _manifest(value.get("requiredAcceptance"), _checklist(value["identityChecklist"]))
        if self._read(f"production/attempts/{_token(value['attemptId'], 'attemptId')}/outcome.json") != value:
            raise MaLiangError("candidate is not the attempt outcome")
        if value["recordType"] in {"generation", "edit"}:
            prepared = self.load_prepared(value["attemptId"])
            delivery = validate_delivery(value["delivery"], root=self.root, verify=True)
            if (value["preparedEventId"] != prepared["eventId"]
                    or delivery["invocationId"] != prepared["invocation"]["invocationId"]
                    or delivery["artifact"] != value["artifact"]
                    or value["recordType"] != prepared["kind"]
                    or value["task"] != prepared["task"]
                    or value["identityChecklist"] != prepared["identityChecklist"]
                    or value["requiredAcceptance"] != prepared["requiredAcceptance"]
                    or value["parent"] != prepared["parent"]):
                raise MaLiangError("candidate does not match prepared request and delivery")
        elif value["recordType"] == "derived":
            parent = self._check_binding(value["parent"])
            if (value["sourceAttemptId"] != parent["attemptId"]
                    or value["task"] != parent["task"]
                    or value["identityChecklist"] != parent["identityChecklist"]
                    or value["requiredAcceptance"] != parent["requiredAcceptance"]):
                raise MaLiangError("derived candidate does not match its source")
        return value

    def binding(self, candidate: Any) -> dict[str, Any]:
        value = self._candidate(candidate)
        return {key: deepcopy(value[key]) for key in ("eventId", "attemptId", "artifact")}

    def _claim(self, attempt_id: str) -> None:
        write_immutable_json(self.root, f"production/attempts/{attempt_id}/claim.json", {"nonce": uuid4().hex})

    def _outcome_path(self, attempt_id: str) -> str:
        return f"production/attempts/{_token(attempt_id, 'attemptId')}/outcome.json"

    def _open_attempt(self, attempt_id: str) -> None:
        if contained_path(self.root, self._outcome_path(attempt_id)).exists():
            raise CollisionError(f"attempt {attempt_id} already has a terminal outcome")

    def _artifact(self, relative: str, data: bytes) -> dict[str, str]:
        write_immutable_bytes(self.root, relative, data)
        return {"path": relative, "sha256": hashlib.sha256(data).hexdigest()}

    def _finish(self, attempt_id: str, value: dict[str, Any]) -> dict[str, Any]:
        write_immutable_json(self.root, self._outcome_path(attempt_id), value)
        return deepcopy(value)

    def prepare(
        self, *, attempt_id: str, task: dict[str, Any], prompt: str,
        parameters: dict[str, Any], inputs: list[dict[str, Any]],
        design_package_sha256: str, provider: str, model: str,
        requested_at: str, identity_checklist: list[str],
        required_acceptance: list[dict[str, str]], kind: str = "generation",
        parent: dict[str, Any] | None = None, edit_instruction: str | None = None,
    ) -> dict[str, Any]:
        attempt_id = _token(attempt_id, "attempt_id")
        task = _object(task, "task")
        if not task:
            raise MaLiangError("task must not be empty")
        checklist = _checklist(identity_checklist)
        manifest = _manifest(required_acceptance, checklist)
        if not isinstance(design_package_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", design_package_sha256):
            raise MaLiangError("design_package_sha256 must be SHA-256")
        if kind not in {"generation", "edit"}:
            raise MaLiangError("prepared kind must be generation or edit")
        if kind == "generation" and (parent is not None or edit_instruction is not None):
            raise MaLiangError("generation cannot contain edit lineage")
        parent_binding = None
        if kind == "edit":
            parent_binding = self.binding(parent)
            _text(edit_instruction, "edit_instruction")
        if not isinstance(inputs, list):
            raise MaLiangError("inputs must be an ordered list")
        checked_inputs = []
        for item in inputs:
            item = _object(item, "input")
            if set(item) != {"artifact", "roles"}:
                raise MaLiangError("input must contain artifact and roles")
            artifact = validate_artifact(item["artifact"], root=self.root, verify=True)
            roles = _checklist(item["roles"])
            checked_inputs.append({"artifact": artifact, "roles": roles})
        request = {
            "prompt": _text(prompt, "prompt"), "parameters": _object(parameters, "parameters"),
            "inputs": checked_inputs, "designPackageSha256": design_package_sha256,
            "task": task, "kind": kind,
        }
        if parent_binding is not None:
            request.update(parent=parent_binding, editInstruction=edit_instruction)
        invocation = validate_invocation({
            "schemaVersion": 1, "attemptId": attempt_id, "provider": provider,
            "model": model, "request": request, "requestedAt": requested_at,
        })
        self._claim(attempt_id)
        value = self._event("prepared", attemptId=attempt_id, kind=kind, task=task,
                            identityChecklist=checklist, requiredAcceptance=manifest,
                            invocation=invocation, parent=parent_binding)
        write_immutable_json(self.root, f"production/attempts/{attempt_id}/prepared.json", value)
        return deepcopy(value)

    def load_prepared(self, attempt_id: str) -> dict[str, Any]:
        value = self._require(self._read(f"production/attempts/{_token(attempt_id, 'attemptId')}/prepared.json"))
        if value["recordType"] != "prepared":
            raise MaLiangError("not a prepared request")
        _manifest(value.get("requiredAcceptance"), _checklist(value["identityChecklist"]))
        validate_invocation(value["invocation"])
        for item in value["invocation"]["request"]["inputs"]:
            validate_artifact(item["artifact"], root=self.root, verify=True)
        if value["parent"] is not None:
            self._check_binding(value["parent"])
        return value

    def _prepared(self, value: Any) -> dict[str, Any]:
        value = self._require(value)
        if value.get("recordType") != "prepared" or self.load_prepared(value["attemptId"]) != value:
            raise MaLiangError("request is not the frozen prepared request")
        self._open_attempt(value["attemptId"])
        return value

    def succeed(self, prepared: dict[str, Any], data: bytes, *, delivered_at: str,
                metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        prepared = self._prepared(prepared)
        if not isinstance(data, bytes):
            raise MaLiangError("artifact data must be bytes")
        attempt_id = prepared["attemptId"]
        artifact = {"path": f"production/artifacts/{attempt_id}/source.bin", "sha256": hashlib.sha256(data).hexdigest()}
        delivery = validate_delivery({"schemaVersion": 1, "invocationId": prepared["invocation"]["invocationId"],
                                     "artifact": artifact, "deliveredAt": delivered_at,
                                     "metadata": _object({} if metadata is None else metadata, "metadata")})
        self._artifact(artifact["path"], data)
        value = self._event(prepared["kind"], attemptId=attempt_id, task=prepared["task"],
                            identityChecklist=prepared["identityChecklist"], requiredAcceptance=prepared["requiredAcceptance"],
                            artifact=artifact,
                            preparedEventId=prepared["eventId"], delivery=delivery, parent=prepared["parent"])
        return self._finish(attempt_id, value)

    def fail(self, prepared: dict[str, Any], *, failed_at: str, category: str,
             message: str, retryable: bool) -> dict[str, Any]:
        prepared = self._prepared(prepared)
        failure = validate_failure({"schemaVersion": 1, "invocationId": prepared["invocation"]["invocationId"],
                                    "failedAt": failed_at, "category": category, "message": message, "retryable": retryable})
        value = self._event("failure", attemptId=prepared["attemptId"], preparedEventId=prepared["eventId"], failure=failure)
        return self._finish(prepared["attemptId"], value)

    def load_candidate(self, attempt_id: str) -> dict[str, Any]:
        return self._candidate(self._read(self._outcome_path(attempt_id)))

    def import_artifact(self, data: bytes, *, attempt_id: str, task: dict[str, Any],
                        identity_checklist: list[str], required_acceptance: list[dict[str, str]],
                        provenance: str, historical: bool = False) -> dict[str, Any]:
        attempt_id = _token(attempt_id, "attempt_id")
        task = _object(task, "task")
        if not task:
            raise MaLiangError("task must not be empty")
        checklist = _checklist(identity_checklist)
        manifest = _manifest(required_acceptance, checklist)
        _text(provenance, "provenance")
        if not isinstance(historical, bool):
            raise MaLiangError("historical must be boolean")
        if not isinstance(data, bytes):
            raise MaLiangError("artifact data must be bytes")
        self._claim(attempt_id)
        artifact = self._artifact(f"production/artifacts/{attempt_id}/source.bin", data)
        value = self._event("historical" if historical else "imported", attemptId=attempt_id,
                            task=task, identityChecklist=checklist, requiredAcceptance=manifest,
                            artifact=artifact, provenance=provenance)
        return self._finish(attempt_id, value)

    def derive(self, parent: dict[str, Any], data: bytes, *, attempt_id: str,
               operation: str, parameters: dict[str, Any]) -> dict[str, Any]:
        parent = self._candidate(parent)
        attempt_id = _token(attempt_id, "attempt_id")
        _text(operation, "operation")
        parameters = _object(parameters, "parameters")
        if not isinstance(data, bytes):
            raise MaLiangError("artifact data must be bytes")
        self._claim(attempt_id)
        artifact = self._artifact(f"production/artifacts/{attempt_id}/source.bin", data)
        value = self._event("derived", attemptId=attempt_id, task=parent["task"],
                            identityChecklist=parent["identityChecklist"], requiredAcceptance=parent["requiredAcceptance"],
                            artifact=artifact,
                            parent=self.binding(parent), sourceAttemptId=parent["attemptId"],
                            operation=operation, parameters=parameters)
        return self._finish(attempt_id, value)

    def _check_binding(self, binding: dict[str, Any]) -> dict[str, Any]:
        candidate = self.load_candidate(binding["attemptId"])
        if {key: candidate[key] for key in ("eventId", "attemptId", "artifact")} != binding:
            raise MaLiangError("candidate binding does not match exact attempt and artifact")
        return candidate

    def record_review(self, candidate: dict[str, Any], *, reviewer: str, actor_type: str,
                      decision: str, checklist: dict[str, str], evidence: dict[str, str],
                      decided_at: str) -> dict[str, Any]:
        candidate = self._candidate(candidate)
        if actor_type != "human":
            raise MaLiangError("human review requires an explicit human decision")
        _text(reviewer, "reviewer")
        if decision not in {"adopt", "reject", "pending"}:
            raise MaLiangError("invalid human decision")
        checklist = _object(checklist, "checklist")
        methods = {item["id"]: item["method"] for item in candidate["requiredAcceptance"]}
        if any(methods.get(item) != "human" for item in checklist):
            raise MaLiangError("human checklist may only contain declared human acceptance items")
        if any(not isinstance(status, str) or status not in {"pass", "fail", "pending", "unsupported"} for status in checklist.values()):
            raise MaLiangError("invalid checklist status")
        # Reuse the workflow's timezone-aware timestamp validation without inventing an invocation.
        from ..workflow import _timestamp
        _timestamp(decided_at, "decided_at")
        evidence = validate_artifact(evidence, root=self.root, verify=True)
        data = read_contained_bytes(self.root, evidence["path"])
        frozen_evidence = self._artifact(f"production/evidence/{evidence['sha256']}.bin", data)
        return self._event("human-review", candidate=self.binding(candidate), reviewer=reviewer,
                           actorType=actor_type, decision=decision, checklist=checklist,
                           evidence=frozen_evidence, sourceEvidence=evidence, decidedAt=decided_at)

    def record_automatic_result(self, candidate: dict[str, Any], *, item_id: str,
                                status: str, evaluator: str, evidence: dict[str, str]) -> dict[str, Any]:
        candidate = self._candidate(candidate)
        methods = {item["id"]: item["method"] for item in candidate["requiredAcceptance"]}
        if not isinstance(item_id, str) or methods.get(item_id) != "automatic":
            raise MaLiangError("automatic result requires a declared automatic acceptance item")
        if not isinstance(status, str) or status not in {"pass", "fail", "pending", "unsupported"}:
            raise MaLiangError("invalid automatic result status")
        _text(evaluator, "evaluator")
        evidence = validate_artifact(evidence, root=self.root, verify=True)
        data = read_contained_bytes(self.root, evidence["path"])
        frozen_evidence = self._artifact(f"production/evidence/{evidence['sha256']}.bin", data)
        return self._event("automatic-result", candidate=self.binding(candidate), itemId=item_id,
                           method="automatic", status=status, evaluator=evaluator,
                           evidence=frozen_evidence, sourceEvidence=evidence)

    def _automatic_results(self, candidate: dict[str, Any], results: Any) -> list[dict[str, Any]]:
        if not isinstance(results, list):
            raise MaLiangError("automatic_results must be a list of result events")
        required = [item["id"] for item in candidate["requiredAcceptance"] if item["method"] == "automatic"]
        by_item = {}
        binding = self.binding(candidate)
        for result in results:
            result = self._require(result)
            if (result["recordType"] != "automatic-result" or result.get("method") != "automatic"
                    or result.get("candidate") != binding):
                raise MaLiangError("automatic result does not bind the exact candidate and method")
            item_id = result.get("itemId")
            if not isinstance(item_id, str) or item_id not in required or item_id in by_item:
                raise MaLiangError("unexpected or duplicate automatic result item")
            if result.get("status") != "pass":
                raise MaLiangError("required automatic acceptance did not pass")
            by_item[item_id] = result
        if any(item not in by_item for item in required):
            raise MaLiangError("required automatic acceptance evidence is missing")
        return [by_item[item] for item in required]

    def _review(self, candidate: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
        review = self._require(review)
        if review["recordType"] != "human-review" or review["candidate"] != self.binding(candidate):
            raise MaLiangError("review does not bind the exact candidate")
        return review

    def _approved_review(self, candidate: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
        review = self._review(candidate, review)
        if review["actorType"] != "human" or review["decision"] != "adopt":
            raise MaLiangError("candidate has no human adoption decision")
        required = [item["id"] for item in candidate["requiredAcceptance"] if item["method"] == "human"]
        if any(review["checklist"].get(item) != "pass" for item in required):
            raise MaLiangError("required human acceptance evidence is incomplete")
        return review

    def adopt(self, candidate: dict[str, Any], review: dict[str, Any], *,
              automatic_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        candidate = self._candidate(candidate)
        review = self._approved_review(candidate, review)
        results = self._automatic_results(candidate, [] if automatic_results is None else automatic_results)
        return self._event("adoption", candidate=self.binding(candidate), reviewEventId=review["eventId"],
                           automaticResultEventIds=[result["eventId"] for result in results])

    def project_current(self, asset_id: str, candidate: dict[str, Any], *,
                        review: dict[str, Any] | None = None, adoption: dict[str, Any] | None = None,
                        source_events: list[str] | None = None) -> Path:
        asset_id = _token(asset_id, "asset_id")
        candidate = self._candidate(candidate)
        sources = [candidate["eventId"]]
        status = "pending"
        results = []
        if adoption is not None:
            adoption = self._require(adoption)
            if adoption["recordType"] != "adoption" or adoption["candidate"] != self.binding(candidate):
                raise MaLiangError("adoption does not bind the exact candidate")
            adopted_review = self._require(self._read(f"production/events/{adoption['reviewEventId']}.json"))
            if review is not None and review != adopted_review:
                raise MaLiangError("projection review differs from adoption review")
            review = adopted_review
            self._approved_review(candidate, review)
            result_ids = adoption.get("automaticResultEventIds")
            if not isinstance(result_ids, list) or any(not isinstance(item, str) or not _EVENT.fullmatch(item) for item in result_ids):
                raise MaLiangError("invalid adoption automatic result event IDs")
            results = self._automatic_results(candidate, [self._read(f"production/events/{item}.json") for item in result_ids])
            if [result["eventId"] for result in results] != result_ids:
                raise MaLiangError("adoption results differ from required acceptance order")
            status = "adopted"
        if review is not None:
            review = self._review(candidate, review)
            sources.append(review["eventId"])
            if adoption is None and review["decision"] == "reject":
                status = "rejected"
        if adoption is not None:
            sources.extend(result["eventId"] for result in results)
            sources.append(adoption["eventId"])
        if source_events is not None and source_events != sources:
            raise MaLiangError("projection source events do not match validated immutable events")
        value = {"schemaVersion": 1, "recordType": "current-projection", "assetId": asset_id,
                 "candidate": self.binding(candidate), "status": status, "sourceEvents": sources}
        destination = contained_path(self.root, f"production/current/{asset_id}.json")
        _assert_plain_path(self.root, destination, include_destination=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        _assert_plain_path(self.root, destination, include_destination=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{asset_id}.", suffix=".tmp", dir=destination.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(canonical_bytes(value))
                stream.flush()
                os.fsync(stream.fileno())
            _assert_plain_path(self.root, destination, include_destination=True)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination
