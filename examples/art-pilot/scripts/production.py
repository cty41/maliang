"""Packet-driven project adapter; no provider execution or inferred human decisions."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from maliang_art.core import canonical_bytes, contained_path, write_immutable_bytes, write_immutable_json
from maliang_art.production import ProductionStore
from maliang_art.authoring import compile_design
from maliang_art.authoring.compiler import audit_alpha_bounds

PROJECT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def default_reviewer(root):
    import getpass
    import subprocess

    def git(key):
        try:
            done = subprocess.run(["git", "-C", str(root), "config", key], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return ""
        return done.stdout.strip() if done.returncode == 0 else ""
    name, email = git("user.name"), git("user.email")
    if name:
        return f"{name} <{email}>" if email else name
    return getpass.getuser()


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


CHARACTER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
CURSOR_PROVIDER = "cursor-desktop"
CURSOR_ASPECT_RATIOS = {"1:1", "4:3", "3:4", "16:9", "9:16"}


def character_of(root, attempt):
    relative = f"production/host-locks/attempts/{attempt}.json"
    return read_json(root, relative)["character"] if source(root, relative).exists() else None


def generation_provider(store, candidate):
    while candidate["recordType"] == "derived":
        candidate = store.load_candidate(candidate["parent"]["attemptId"])
    if candidate["recordType"] not in {"generation", "edit"}:
        return None
    return store.load_prepared(candidate["attemptId"])["invocation"]["provider"]


def check_host_lock(root, store, character, provider, model, parent, new_character=False):
    """One character keeps the image host and model of its first generation request."""
    if not isinstance(character, str) or not CHARACTER.fullmatch(character):
        raise ValueError("character must be a portable identifier")
    if provider.lower().startswith("cursor") and provider != CURSOR_PROVIDER:
        raise ValueError(f"Cursor host provider must be exactly {CURSOR_PROVIDER!r}")
    lock_path = source(root, f"production/host-locks/{character}.json")
    if not lock_path.exists() and not new_character:
        existing = sorted(p.stem for p in lock_path.parent.glob("*.json")) if lock_path.parent.exists() else []
        if existing:
            raise ValueError(f"character {character!r} has no lock; existing characters are {existing}. "
                             "Pass --new-character only if this is really a new character")
    if lock_path.exists():
        lock = read_json(root, f"production/host-locks/{character}.json")
        if (lock["provider"], lock["model"]) != (provider, model):
            raise ValueError(f"character {character} is locked to provider {lock['provider']!r} "
                             f"model {lock['model']!r}; start a new character to change hosts")
    if parent is not None:
        if character_of(root, parent["attemptId"]) != character:
            raise ValueError("edit parent belongs to a different or unrecorded character")
        if generation_provider(store, parent) not in {None, provider}:
            raise ValueError("edit parent was generated by a different provider")


def record_character(root, attempt, character, provider=None, model=None):
    if provider is not None and not source(root, f"production/host-locks/{character}.json").exists():
        write_immutable_json(root, f"production/host-locks/{character}.json", {
            "character": character, "provider": provider, "model": model,
            "firstAttemptId": attempt, "lockedAt": now()})
    write_immutable_json(root, f"production/host-locks/attempts/{attempt}.json",
                         {"attemptId": attempt, "character": character})


def bind_success(root, store, prepared, receipt_path, image):
    receipt = read_json(root, receipt_path)
    if (receipt.get("preparedEventId") != prepared["eventId"] or
        receipt.get("invocation") != prepared["invocation"] or
        receipt.get("outcome") != "success" or
        not isinstance(receipt.get("executionEvidence"), str) or not receipt["executionEvidence"].strip()):
        raise ValueError("receipt must attest the exact frozen invocation and execution evidence")
    if receipt.get("artifactSha256") != digest(image):
        raise ValueError("receipt output hash differs from delivery")
    return store.succeed(prepared, image, delivered_at=now(), metadata={"receipt": freeze_artifact(root, receipt_path)})


def cursor_prepared(root, store, attempt):
    prepared = store.load_prepared(attempt)
    if prepared["invocation"]["provider"] != CURSOR_PROVIDER:
        raise ValueError(f"attempt provider must be {CURSOR_PROVIDER}")
    if source(root, f"production/attempts/{attempt}/outcome.json").exists():
        raise ValueError(f"attempt {attempt} already has a terminal outcome")
    return prepared


def decoded_format(data):
    from io import BytesIO
    from PIL import Image
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > 2048 ** 2:
            raise ValueError("image exceeds 4194304 pixel decode budget")
        image.load()
        return image.format


def cursor_packet(root, store, attempt):
    """Build GenerateImage arguments the host agent must pass verbatim; it cannot call the tool itself."""
    prepared = cursor_prepared(root, store, attempt)
    request = prepared["invocation"]["request"]
    unsupported = sorted(set(request["parameters"]) - {"aspect_ratio"})
    if unsupported:
        raise ValueError(f"Cursor GenerateImage does not support parameters: {', '.join(unsupported)}")
    call = {"description": request["prompt"]}
    paths = []
    for item in request["inputs"]:
        data = source(root, item["artifact"]["path"]).read_bytes()
        if digest(data) != item["artifact"]["sha256"]:
            raise ValueError("frozen input hash mismatch")
        extension = {"PNG": "png", "JPEG": "jpg"}.get(decoded_format(data))
        if extension is None:
            raise ValueError("Cursor reference inputs must be PNG or JPEG")
        paths.append(str(write_immutable_bytes(root, f"production/cursor-inputs/{digest(data)}.{extension}", data)))
    if paths:
        call["reference_image_paths"] = paths
    if "aspect_ratio" in request["parameters"]:
        if request["parameters"]["aspect_ratio"] not in CURSOR_ASPECT_RATIOS:
            raise ValueError(f"aspect_ratio must be one of {sorted(CURSOR_ASPECT_RATIOS)}")
        call["aspect_ratio"] = request["parameters"]["aspect_ratio"]
    call["filename"] = f"{attempt}.png"
    relative = f"production/attempts/{attempt}/cursor-call.json"
    if source(root, relative).exists():
        raise ValueError(f"attempt {attempt} already has a Cursor call packet")
    path = write_immutable_json(root, relative, call)
    return {"call": call, "path": str(path), "sha256": digest(path.read_bytes())}


def cursor_complete(root, store, attempt, output):
    prepared = cursor_prepared(root, store, attempt)
    packet_path = source(root, f"production/attempts/{attempt}/cursor-call.json")
    if not packet_path.exists():
        raise ValueError("run cursor-packet before cursor-complete")
    output = Path(output).resolve()
    if output.stem != attempt or output.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError(f"Cursor output must be named {attempt}.png/.jpg/.jpeg")
    if output.stat().st_mtime <= packet_path.stat().st_mtime:
        raise ValueError("Cursor output predates the call packet")
    image = output.read_bytes()
    decoded_format(image)
    write_immutable_bytes(root, f"production/cursor-outputs/{attempt}{output.suffix.lower()}", image)
    packet_sha = digest(packet_path.read_bytes())
    receipt_path = f"production/attempts/{attempt}/cursor-receipt.json"
    write_immutable_json(root, receipt_path, {
        "preparedEventId": prepared["eventId"], "invocation": prepared["invocation"], "outcome": "success",
        "artifactSha256": digest(image),
        "executionEvidence": (f"host-agent-attested: Cursor GenerateImage called by the host agent with the "
                              f"cursor-call.json packet sha256 {packet_sha}; tool-reported output {output.as_posix()}. "
                              "The call arguments were not machine-observed; model and billing unknown.")})
    return bind_success(root, store, prepared, receipt_path, image)


def preview(root, store, attempt):
    """Write a correctly named viewing copy and report absolute paths; records no event."""
    candidate = store.load_candidate(attempt)
    data = source(root, candidate["artifact"]["path"]).read_bytes()
    extension = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}.get(decoded_format(data), "bin")
    copy = source(root, f"previews/{attempt}.{extension}")
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(data)
    origin = candidate
    while origin["recordType"] == "derived":
        origin = store.load_candidate(origin["parent"]["attemptId"])
    outputs = sorted((root / "production/cursor-outputs").glob(f"{origin['attemptId']}.*"))
    return {"attemptId": attempt, "eventId": candidate["eventId"],
            "candidate": {"path": str(source(root, candidate["artifact"]["path"])), "sha256": candidate["artifact"]["sha256"]},
            "hostOutputCopy": str(outputs[0]) if outputs else None,
            "viewingCopy": {"path": str(copy), "evidence": False}}


def record_human_decision(root, store, candidate, decision, evidence_path):
    if (decision.get("actorType") != "human" or decision.get("candidate") != store.binding(candidate)
            or decision.get("identityChecklist") != candidate["identityChecklist"]
            or not isinstance(decision.get("statement"), str) or not decision["statement"].strip()):
        raise ValueError("actual human statement must bind the candidate and compiled identity checklist")
    return store.record_review(candidate, reviewer=decision["reviewer"], actor_type="human",
        decision=decision["decision"], checklist=decision["checklist"],
        evidence=freeze_artifact(root, evidence_path), decided_at=decision["decidedAt"])


def revisions(root, character):
    """Rejected chat-relayed reviews of one character: prompt material, not record changes."""
    notes = []
    for lock in sorted((root / "production/host-locks/attempts").glob("*.json")):
        if read_json(root, f"production/host-locks/attempts/{lock.name}")["character"] != character:
            continue
        for path in sorted((root / f"production/quick-reviews/{lock.stem}").glob("*.json")):
            decision = read_json(root, path.relative_to(root).as_posix())
            if decision["decision"] == "reject":
                notes.append({"attemptId": lock.stem, "decidedAt": decision["decidedAt"],
                              "statement": decision["statement"], **decision["revisionNotes"]})
    return sorted(notes, key=lambda n: n["decidedAt"])


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
    prepare.add_argument("--character", required=True, help="character ID; locks the image host of its first request")
    prepare.add_argument("--new-character", action="store_true",
                         help="confirm an unlocked character ID when other characters already have locks")
    cursor_packet_cmd = commands.add_parser("cursor-packet")
    cursor_packet_cmd.add_argument("--attempt", required=True)
    cursor_complete_cmd = commands.add_parser("cursor-complete")
    cursor_complete_cmd.add_argument("--attempt", required=True)
    cursor_complete_cmd.add_argument("--output", required=True, help="output path reported by Cursor GenerateImage")
    cursor_fail_cmd = commands.add_parser("cursor-fail")
    cursor_fail_cmd.add_argument("--attempt", required=True)
    cursor_fail_cmd.add_argument("--message", required=True)
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
    quick = commands.add_parser("review-quick", help="record a human choice relayed from the host chat")
    quick.add_argument("--attempt", required=True)
    quick.add_argument("--choice", choices=["pass", "reject"], required=True)
    quick.add_argument("--quote", required=True, help="the user's own words for this choice")
    quick.add_argument("--issues", default="", help="comma-separated human acceptance IDs the user marked unsatisfied")
    quick.add_argument("--note", default="", help="the user's free-form improvement request")
    quick.add_argument("--reviewer", help="default: git user.name <user.email>, else the OS user")
    view = commands.add_parser("preview", help="write previews/<attempt>.<ext> and print absolute paths")
    view.add_argument("--attempt", required=True)
    notes = commands.add_parser("revisions", help="list rejected chat-review issues and notes of a character")
    notes.add_argument("--character", required=True)
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
            parent = store.load_candidate(args.parent) if args.parent else None
            check_host_lock(root, store, args.character, args.provider, args.model, parent, args.new_character)
            if parent is not None:
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
                parent=parent, edit_instruction=args.instruction)
            record_character(root, args.attempt, args.character, args.provider, args.model)
    elif args.command == "complete":
        result = bind_success(root, store, store.load_prepared(args.attempt), args.receipt,
                              source(root, args.image).read_bytes())
    elif args.command == "cursor-packet":
        result = cursor_packet(root, store, args.attempt)
    elif args.command == "cursor-complete":
        result = cursor_complete(root, store, args.attempt, args.output)
    elif args.command == "cursor-fail":
        result = store.fail(cursor_prepared(root, store, args.attempt), failed_at=now(), category="host-error",
                            message=args.message, retryable=False)
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
        if character_of(root, parent["attemptId"]) is not None:
            record_character(root, args.attempt, character_of(root, parent["attemptId"]))
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
        result = record_human_decision(root, store, candidate, read_json(root, args.decision_file), args.decision_file)
    elif args.command == "review-quick":
        candidate = store.load_candidate(args.attempt)
        human = [item["id"] for item in candidate["requiredAcceptance"] if item["method"] == "human"]
        issues = [i.strip() for i in args.issues.split(",") if i.strip()]
        unknown = [i for i in issues if i not in human]
        if unknown:
            raise ValueError(f"unknown human acceptance IDs {unknown}; choose from {human}")
        if not args.quote.strip():
            raise ValueError("quote the user's own words for this choice")
        if args.choice == "pass" and (issues or args.note.strip()):
            raise ValueError("a pass cannot carry unsatisfied issues or improvement notes")
        status = "pass" if args.choice == "pass" else "pending"
        checklist = {i: "fail" if i in issues else status for i in human}
        decision = {"actorType": "human", "capturedVia": "host-chat", "candidate": store.binding(candidate),
            "identityChecklist": candidate["identityChecklist"], "reviewer": args.reviewer or default_reviewer(root),
            "decision": "adopt" if args.choice == "pass" else "reject", "checklist": checklist,
            "statement": f"Choice relayed by the host agent from chat; user said: {args.quote.strip()}",
            "revisionNotes": {"issues": issues, "note": args.note.strip()}, "decidedAt": now()}
        path = f"production/quick-reviews/{args.attempt}/{digest(canonical_bytes(decision))}.json"
        write_immutable_json(root, path, decision)
        result = record_human_decision(root, store, candidate, decision, path)
    elif args.command == "preview":
        result = preview(root, store, args.attempt)
    elif args.command == "revisions":
        result = revisions(root, args.character)
    else:
        candidate = store.load_candidate(args.attempt)
        review = read_json(root, args.review)
        result = store.adopt(candidate, review, automatic_results=[read_json(root, p) for p in args.result])
        store.project_current(args.asset, candidate, adoption=result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
