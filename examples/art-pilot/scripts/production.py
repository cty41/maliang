"""Packet-driven project adapter; no provider execution or inferred human decisions."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from maliang_art.core import canonical_bytes, contained_path, write_immutable_bytes, write_immutable_json
from maliang_art.production import ProductionStore
from maliang_art.authoring import compile_design
from maliang_art.authoring.compiler import audit_alpha_bounds

PROJECT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source(root, relative):
    if Path(relative).is_absolute():
        raise ValueError("source paths must be relative to the project root")
    return contained_path(root, relative)


def read_json(root, relative):
    return json.loads(source(root, relative).read_text(encoding="utf-8"))


def acceptance(packet):
    manifest, seen = [], set()
    for item in packet["acceptance"]:
        item_id = item["id"]
        if not isinstance(item_id, str) or not item_id.strip() or item_id in seen:
            raise ValueError("empty or duplicate acceptance ID")
        seen.add(item_id)
        method = {"alpha-bounds": "automatic", "human": "human"}.get(item["method"])
        if method is None:
            raise ValueError(f"unknown acceptance method: {item['method']}")
        if type(item["required"]) is not bool:
            raise ValueError("required must be boolean")
        if item["required"]:
            manifest.append({"id": item_id, "method": method})
    if {"id": "identity", "method": "human"} not in manifest:
        raise ValueError("compiled identity must be required human acceptance")
    return manifest


def freeze_artifact(root, relative):
    data = source(root, relative).read_bytes()
    path = f"production/inputs/{digest(data)}.bin"
    write_immutable_bytes(root, path, data)
    return {"path": path, "sha256": digest(data)}


def frozen_packet(root, store, candidate):
    original = candidate
    while original["recordType"] == "derived":
        original = store.load_candidate(original["parent"]["attemptId"])
    if original["recordType"] in {"generation", "edit"}:
        sha = store.load_prepared(original["attemptId"])["invocation"]["request"]["designPackageSha256"]
    else:
        sha = original["task"]["designPackageSha256"]
    if digest(source(root, f"production/designs/{sha}.json").read_bytes()) != sha:
        raise ValueError("frozen design hash mismatch")
    return read_json(root, f"production/designs/{sha}.json"), sha


def matte_resize(data, targets, key_color=None, tolerance=24):
    """Key edge-connected background only, so interior colors near the key stay opaque."""
    from collections import deque
    from io import BytesIO
    from PIL import Image
    if not 0 <= tolerance <= 255:
        raise ValueError("tolerance must be within 0..255")
    with Image.open(BytesIO(data)) as header:
        if header.width * header.height > 2048 ** 2:
            raise ValueError("matte image exceeds 4194304 pixel decode budget")
        image = header.convert("RGBA")
    sw, sh = targets["sourceSize"]
    if image.size != (sw, sh):
        raise ValueError(f"parent size {list(image.size)} differs from frozen sourceSize {[sw, sh]}")
    ow, oh = targets["outputSize"]
    if ow * sh != oh * sw:
        raise ValueError("outputSize must keep the sourceSize aspect ratio")
    pixels = image.load()
    if key_color is None:
        corners = [pixels[x, y][:3] for x, y in ((0, 0), (sw - 1, 0), (0, sh - 1), (sw - 1, sh - 1))]
        key = tuple(sorted(c[i] for c in corners)[1] for i in range(3))
        key_source = "corners"
    else:
        text = key_color.removeprefix("#")
        if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
            raise ValueError("key color must be #RRGGBB")
        key = tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
        key_source = "explicit"
    near = lambda p: max(abs(p[i] - key[i]) for i in range(3)) <= tolerance
    seen = bytearray(sw * sh)
    queue = deque()
    for x in range(sw):
        queue.extend(((x, 0), (x, sh - 1)))
    for y in range(sh):
        queue.extend(((0, y), (sw - 1, y)))
    while queue:
        x, y = queue.popleft()
        index = y * sw + x
        if seen[index] or not near(pixels[x, y]):
            continue
        seen[index] = 1
        pixels[x, y] = (0, 0, 0, 0)
        if x > 0: queue.append((x - 1, y))
        if x < sw - 1: queue.append((x + 1, y))
        if y > 0: queue.append((x, y - 1))
        if y < sh - 1: queue.append((x, y + 1))
    box = image.getchannel("A").getbbox()
    if box is None:
        raise ValueError("matte left no opaque subject")
    if box[0] == 0 or box[1] == 0 or box[2] == sw or box[3] == sh:
        raise ValueError("matted subject touches the source canvas edge")
    scale = ow / sw
    subject = image.crop(box)
    size = (max(1, round(subject.width * scale)), max(1, round(subject.height * scale)))
    subject = subject.resize(size, Image.LANCZOS)
    left = round(targets["anchorX"] * scale - size[0] / 2)
    top = round(targets["groundY"] * scale) - size[1]
    if left < 0 or top < 0 or left + size[0] > ow or top + size[1] > oh:
        raise ValueError("placed subject would leave the output canvas")
    canvas = Image.new("RGBA", (ow, oh), (0, 0, 0, 0))
    canvas.paste(subject, (left, top))
    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue(), {
        "keyColor": "#%02X%02X%02X" % key, "keyColorSource": key_source, "tolerance": tolerance,
        "floodFrom": "edges", "sourceSize": [sw, sh], "outputSize": [ow, oh], "scale": scale,
        "resample": "LANCZOS", "sourceBox": list(box), "placedBox": [left, top, left + size[0], top + size[1]],
        "anchorX": targets["anchorX"], "groundY": targets["groundY"]}


def packet_data(root, relative, contract_path, draft_path):
    data = source(root, relative).read_bytes()
    packet = json.loads(data)
    manifest = acceptance(packet)
    contract = source(root, contract_path).read_bytes()
    draft = source(root, draft_path).read_bytes()
    authoritative = compile_design(json.loads(contract), json.loads(draft)).document
    fields = ("prompt", "tasks", "imageInputs", "acceptance", "designId", "targets",
              "camera", "identityInvariant", "references", "palettePlan", "contextBoard", "comparisonPlan", "familyId")
    for field in fields:
        if field not in packet or canonical_bytes(packet[field]) != canonical_bytes(authoritative[field]):
            raise ValueError(f"compiled packet differs from authoritative contract/draft: {field}")
    return data, packet, manifest, contract, draft


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=str(PROJECT))
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--attempt", required=True)
    prepare.add_argument("--design", required=True)
    prepare.add_argument("--task-index", type=int, default=0)
    prepare.add_argument("--parameters", required=True, help="project-relative backend parameter JSON")
    prepare.add_argument("--provider", required=True)
    prepare.add_argument("--model", default="unknown")
    prepare.add_argument("--parent")
    prepare.add_argument("--instruction")
    complete = commands.add_parser("complete")
    complete.add_argument("--attempt", required=True)
    complete.add_argument("--receipt", required=True, help="actual invocation receipt JSON")
    complete.add_argument("--image", required=True)
    fail = commands.add_parser("fail")
    fail.add_argument("--attempt", required=True)
    fail.add_argument("--category", required=True)
    fail.add_argument("--message", required=True)
    imp = commands.add_parser("import")
    imp.add_argument("--attempt", required=True)
    imp.add_argument("--design", required=True)
    imp.add_argument("--task-index", type=int, default=0)
    imp.add_argument("--image", required=True)
    imp.add_argument("--provenance", required=True)
    imp.add_argument("--historical", action="store_true")
    derive = commands.add_parser("derive")
    derive.add_argument("--attempt", required=True)
    derive.add_argument("--parent", required=True)
    derive.add_argument("--operation", choices=["flip-x", "copy", "matte-resize"], required=True)
    derive.add_argument("--key-color", help="matte-resize background #RRGGBB; default is the corner median")
    derive.add_argument("--tolerance", type=int, default=24, help="matte-resize max RGB channel difference")
    technical = commands.add_parser("technical")
    technical.add_argument("--attempt", required=True)
    review = commands.add_parser("review")
    review.add_argument("--attempt", required=True)
    review.add_argument("--decision-file", required=True)
    adopt = commands.add_parser("adopt")
    adopt.add_argument("--attempt", required=True)
    adopt.add_argument("--review", required=True, help="project-relative human review event JSON")
    adopt.add_argument("--result", action="append", default=[])
    adopt.add_argument("--asset", required=True)
    extract = commands.add_parser("acceptance")
    extract.add_argument("--design", required=True)
    for command in (prepare, imp, extract):
        command.add_argument("--contract", required=True, help="authoritative project-relative family contract JSON")
        command.add_argument("--draft", required=True, help="authoritative project-relative Draft JSON")
    args = parser.parse_args(argv)
    root = Path(args.project).resolve()
    store = ProductionStore(root)
    if args.command == "acceptance":
        result = packet_data(root, args.design, args.contract, args.draft)[2]
    elif args.command in {"prepare", "import"}:
        data, packet, manifest, contract, draft = packet_data(root, args.design, args.contract, args.draft)
        if args.task_index < 0:
            raise ValueError("task index must be nonnegative")
        task = packet["tasks"][args.task_index]
        design_path = f"production/designs/{digest(data)}.json"
        write_immutable_bytes(root, design_path, data)
        write_immutable_bytes(root, f"production/authoring/{digest(contract)}.json", contract)
        write_immutable_bytes(root, f"production/authoring/{digest(draft)}.json", draft)
        write_immutable_json(root, f"production/designs/{digest(data)}.authoring.json", {
            "contract": {"path": f"production/authoring/{digest(contract)}.json", "sha256": digest(contract)},
            "draft": {"path": f"production/authoring/{digest(draft)}.json", "sha256": digest(draft)}})
        if args.command == "import":
            result = store.import_artifact(source(root, args.image).read_bytes(), attempt_id=args.attempt,
                task={**task, "designPackageSha256": digest(data)}, identity_checklist=["identity"],
                required_acceptance=manifest, provenance=args.provenance, historical=args.historical)
        else:
            if bool(args.parent) != bool(args.instruction):
                raise ValueError("edit requires both parent and instruction")
            inputs = []
            if args.parent:
                parent = store.load_candidate(args.parent)
                inputs.append({"artifact": parent["artifact"], "roles": ["edit-source"]})
            for item in packet["imageInputs"]:
                if "construction" in item["roles"] or "debug-layout" in item["roles"]:
                    raise ValueError("debug layout cannot be a production image input")
                artifact = freeze_artifact(root, item["path"])
                if artifact["sha256"] != item["sha256"]:
                    raise ValueError("compiled reference hash differs from actual input")
                inputs.append({"artifact": artifact, "roles": item["roles"]})
            result = store.prepare(attempt_id=args.attempt, task=task, prompt=packet["prompt"],
                parameters=read_json(root, args.parameters), inputs=inputs,
                design_package_sha256=digest(data), provider=args.provider, model=args.model,
                requested_at=now(), identity_checklist=["identity"], required_acceptance=manifest,
                kind="edit" if args.parent else "generation",
                parent=parent if args.parent else None, edit_instruction=args.instruction)
    elif args.command == "complete":
        prepared = store.load_prepared(args.attempt)
        receipt = read_json(root, args.receipt)
        expected = prepared["invocation"]
        if (receipt.get("preparedEventId") != prepared["eventId"] or
            receipt.get("invocation") != expected or
            receipt.get("outcome") != "success" or
            not isinstance(receipt.get("executionEvidence"), str) or not receipt["executionEvidence"].strip()):
            raise ValueError("receipt must attest the exact frozen invocation and execution evidence")
        image = source(root, args.image).read_bytes()
        if receipt.get("artifactSha256") != digest(image):
            raise ValueError("receipt output hash differs from delivery")
        receipt_artifact = freeze_artifact(root, args.receipt)
        result = store.succeed(prepared, image, delivered_at=now(), metadata={"receipt": receipt_artifact})
    elif args.command == "fail":
        result = store.fail(store.load_prepared(args.attempt), failed_at=now(), category=args.category,
                            message=args.message, retryable=False)
    elif args.command == "derive":
        from io import BytesIO
        from PIL import Image, ImageOps
        parent = store.load_candidate(args.parent)
        data = source(root, parent["artifact"]["path"]).read_bytes()
        parameters = {}
        if args.operation == "matte-resize":
            packet, sha = frozen_packet(root, store, parent)
            data, parameters = matte_resize(data, packet["targets"], args.key_color, args.tolerance)
            parameters["designPackageSha256"] = sha
        elif args.operation == "flip-x":
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > 2048 ** 2:
                    raise ValueError("mirror image exceeds 4194304 pixel decode budget")
                output = BytesIO()
                ImageOps.mirror(image).save(output, format="PNG")
                data = output.getvalue()
        result = store.derive(parent, data, attempt_id=args.attempt, operation=args.operation, parameters=parameters)
    elif args.command == "technical":
        candidate = store.load_candidate(args.attempt)
        packet = frozen_packet(root, store, candidate)[0]
        result = []
        for item in packet["acceptance"]:
            if not item["required"] or item["method"] != "alpha-bounds":
                continue
            size = item.get("parameters", {}).get("outputSize", packet["targets"]["outputSize"])
            report = audit_alpha_bounds(source(root, candidate["artifact"]["path"]).read_bytes(), size)
            report.update(candidate=store.binding(candidate), itemId=item["id"], evaluator="alpha-bounds")
            path = f"production/technical/{args.attempt}/{item['id']}.json"
            write_immutable_json(root, path, report)
            result.append(store.record_automatic_result(candidate, item_id=item["id"], status=report["status"],
                evaluator="alpha-bounds", evidence=freeze_artifact(root, path)))
    elif args.command == "review":
        candidate = store.load_candidate(args.attempt)
        decision = read_json(root, args.decision_file)
        if (decision.get("actorType") != "human" or decision.get("candidate") != store.binding(candidate)
                or decision.get("identityChecklist") != candidate["identityChecklist"]
                or not isinstance(decision.get("statement"), str) or not decision["statement"].strip()):
            raise ValueError("actual human statement must bind the candidate and compiled identity checklist")
        result = store.record_review(candidate, reviewer=decision["reviewer"], actor_type="human",
            decision=decision["decision"], checklist=decision["checklist"],
            evidence=freeze_artifact(root, args.decision_file), decided_at=decision["decidedAt"])
    else:
        candidate = store.load_candidate(args.attempt)
        review = read_json(root, args.review)
        result = store.adopt(candidate, review, automatic_results=[read_json(root, p) for p in args.result])
        store.project_current(args.asset, candidate, adoption=result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
