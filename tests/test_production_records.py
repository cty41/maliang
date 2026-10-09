from __future__ import annotations

import copy
import hashlib
import io
import json

from PIL import Image
import pytest

from maliang_art.core import CollisionError, MaLiangError
from maliang_art.production import ProductionStore


SHA = 'a' * 64
TIME = '2026-01-01T00:00:00Z'


def png(color='red'):
    stream = io.BytesIO()
    Image.new('RGBA', (2, 2), color).save(stream, format='PNG')
    return stream.getvalue()


def prepare(store, attempt='a001', **kwargs):
    values = dict(attempt_id=attempt, task={'view': 'DR', 'state': 'Idle'},
                  prompt='Draw a synthetic capsule.', parameters={'seed': 7},
                  inputs=[], design_package_sha256=SHA, provider='offline',
                  model='unknown', requested_at=TIME, identity_checklist=['species', 'mark'])
    values.update(kwargs)
    values.setdefault('required_acceptance', [{'id': item, 'method': 'human'} for item in values['identity_checklist']])
    return store.prepare(**values)


def candidate(store, attempt='a001', color='red'):
    request = prepare(store, attempt)
    return store.succeed(request, png(color), delivered_at=TIME, metadata={'adapter': 'offline'})


def evidence(tmp_path):
    data = b'{"userDecision":"adopt","checklist":["species","mark"]}'
    (tmp_path / 'decision.json').write_bytes(data)
    return {'path': 'decision.json', 'sha256': hashlib.sha256(data).hexdigest()}


def review(store, item, tmp_path, **kwargs):
    values = dict(reviewer='project artist', actor_type='human', decision='adopt',
                  checklist={'species': 'pass', 'mark': 'pass'},
                  evidence=evidence(tmp_path), decided_at=TIME)
    values.update(kwargs)
    return store.record_review(item, **values)


def test_request_is_published_before_adapter_and_detached(tmp_path):
    store = ProductionStore(tmp_path)
    request = prepare(store)
    assert store.load_prepared('a001') == request
    assert request['invocation']['model'] == 'unknown'
    assert request['invocation']['request']['designPackageSha256'] == SHA
    request['invocation']['request']['parameters']['seed'] = 99
    with pytest.raises(MaLiangError):
        store.succeed(request, png(), delivered_at=TIME)
    assert store.load_prepared('a001')['invocation']['request']['parameters']['seed'] == 7


def test_inputs_preserve_order_roles_and_hashes_and_are_checked(tmp_path):
    store = ProductionStore(tmp_path)
    first = store.import_artifact(png(), attempt_id='ref1', task={'view': 'DR'}, identity_checklist=['species'], required_acceptance=[{'id': 'species', 'method': 'human'}], provenance='synthetic reference')
    second = store.import_artifact(png('blue'), attempt_id='ref2', task={'view': 'UL'}, identity_checklist=['species'], required_acceptance=[{'id': 'species', 'method': 'human'}], provenance='synthetic reference')
    inputs = [{'artifact': second['artifact'], 'roles': ['style']}, {'artifact': first['artifact'], 'roles': ['identity', 'shape']}]
    request = prepare(store, inputs=inputs)
    assert request['invocation']['request']['inputs'] == inputs
    broken = copy.deepcopy(inputs); broken[0]['artifact']['sha256'] = SHA
    with pytest.raises(MaLiangError):
        prepare(store, 'a002', inputs=broken)


def test_independent_attempts_and_immutable_outcomes(tmp_path):
    store = ProductionStore(tmp_path)
    first = candidate(store)
    second = candidate(store, 'a002', 'blue')
    assert first['attemptId'] != second['attemptId']
    assert first['artifact']['path'] != second['artifact']['path']
    with pytest.raises(CollisionError):
        prepare(store)
    with pytest.raises(CollisionError):
        store.succeed(store.load_prepared('a001'), png('blue'), delivered_at=TIME)
    assert store.load_candidate('a001') == first


def test_edit_binds_exact_parent_and_instruction(tmp_path):
    store = ProductionStore(tmp_path)
    parent = candidate(store)
    request = prepare(store, 'edit1', kind='edit', parent=parent, edit_instruction='Change only the outline.')
    edited = store.succeed(request, png('blue'), delivered_at=TIME)
    assert request['parent'] == store.binding(parent)
    assert request['invocation']['request']['editInstruction'] == 'Change only the outline.'
    assert edited['parent'] == store.binding(parent)
    with pytest.raises(MaLiangError):
        prepare(store, 'edit2', kind='edit', parent=parent)


def test_failure_is_terminal_and_retry_has_new_attempt(tmp_path):
    store = ProductionStore(tmp_path)
    request = prepare(store)
    failure = store.fail(request, failed_at=TIME, category='timeout', message='offline timeout', retryable=True)
    assert failure['recordType'] == 'failure'
    with pytest.raises(CollisionError):
        store.succeed(request, png(), delivered_at=TIME)
    with pytest.raises(MaLiangError):
        store.load_candidate('a001')
    assert candidate(store, 'retry1')['attemptId'] == 'retry1'


def test_import_honest_history_and_derived_lineage(tmp_path):
    store = ProductionStore(tmp_path)
    imported = store.import_artifact(png(), attempt_id='old1', task={'view': 'DR', 'state': 'Idle'}, identity_checklist=['species'], required_acceptance=[{'id': 'species', 'method': 'human'}], provenance='historical image; invocation unknown', historical=True)
    assert imported['recordType'] == 'historical'
    assert 'invocation' not in imported and 'requestedAt' not in imported
    derived = store.derive(imported, png('blue'), attempt_id='flip1', operation='flipX', parameters={'axis': 'horizontal'})
    assert derived['parent'] == store.binding(imported)
    assert derived['sourceAttemptId'] == 'old1'
    assert derived['parameters'] == {'axis': 'horizontal'}
    assert derived['recordType'] == 'derived'


@pytest.mark.parametrize('change', [dict(actor_type='agent'), dict(decision='pending'), dict(decision='reject'), dict(checklist={'species': 'pass', 'mark': 'pending'}), dict(checklist={'species': 'pass'})])
def test_no_automatic_or_incomplete_adoption(tmp_path, change):
    store = ProductionStore(tmp_path)
    item = candidate(store)
    with pytest.raises(MaLiangError):
        decision = review(store, item, tmp_path, **change)
        store.adopt(item, decision)


def test_exact_candidate_review_not_transferable_and_direct_adoption(tmp_path):
    store = ProductionStore(tmp_path)
    first = candidate(store)
    approved = review(store, first, tmp_path)
    adoption = store.adopt(first, approved)
    assert adoption['candidate'] == store.binding(first)
    second = candidate(store, 'a002')  # even identical bytes do not transfer approval
    with pytest.raises(MaLiangError):
        store.adopt(second, approved)
    changed = copy.deepcopy(approved); changed['checklist']['mark'] = 'pass '
    with pytest.raises(MaLiangError):
        store.adopt(first, changed)


def test_projection_is_atomic_and_validates_sources(tmp_path, monkeypatch):
    import maliang_art.production.store as module
    store = ProductionStore(tmp_path)
    first = candidate(store)
    adopted = store.adopt(first, review(store, first, tmp_path))
    path = store.project_current('falcon', first, adoption=adopted)
    previous = path.read_bytes()
    assert json.loads(previous)['status'] == 'adopted'
    second = candidate(store, 'a002', 'blue')
    with pytest.raises(MaLiangError):
        store.project_current('falcon', second, adoption=adopted)
    with pytest.raises(MaLiangError):
        store.project_current('falcon', second, source_events=[first['eventId']])
    def crash(*args):
        raise OSError('simulated power interruption before replacement')
    monkeypatch.setattr(module.os, 'replace', crash)
    with pytest.raises(OSError):
        store.project_current('falcon', second)
    assert path.read_bytes() == previous
    assert store.load_candidate('a001') == first
    assert not list(path.parent.glob('*.tmp'))


def test_projection_pending_rejected_and_no_source_overwrite(tmp_path):
    store = ProductionStore(tmp_path)
    first = candidate(store)
    rejected = review(store, first, tmp_path, decision='reject')
    assert json.loads(store.project_current('falcon', first, review=rejected).read_bytes())['status'] == 'rejected'
    second = candidate(store, 'a002')
    assert json.loads(store.project_current('falcon', second).read_bytes())['status'] == 'pending'
    with pytest.raises(MaLiangError):
        store.project_current('../artifacts/a001/source.png', first)
    assert store.load_candidate('a001') == first


def test_invalid_bindings_and_external_artifact_tampering(tmp_path):
    store = ProductionStore(tmp_path)
    item = candidate(store)
    (tmp_path / item['artifact']['path']).write_bytes(png('blue'))
    with pytest.raises(MaLiangError):
        store.derive(item, png(), attempt_id='bad', operation='copy', parameters={})
    with pytest.raises(MaLiangError):
        store.project_current('falcon', item)


def test_projection_accepts_only_exact_persisted_sources(tmp_path):
    store = ProductionStore(tmp_path)
    item = candidate(store)
    approval = review(store, item, tmp_path)
    adoption = store.adopt(item, approval)
    sources = [item['eventId'], approval['eventId'], adoption['eventId']]
    path = store.project_current('falcon', item, adoption=adoption, source_events=sources)
    assert json.loads(path.read_bytes())['sourceEvents'] == sources
    original = path.read_bytes()
    event_path = tmp_path / 'production/events' / (approval['eventId'] + '.json')
    event_path.write_text('{}', encoding='utf-8')
    with pytest.raises(MaLiangError):
        store.project_current('falcon', item, adoption=adoption)
    assert path.read_bytes() == original


def test_review_freezes_evidence_without_overwriting_source(tmp_path):
    store = ProductionStore(tmp_path)
    item = candidate(store)
    approval = review(store, item, tmp_path)
    original = (tmp_path / 'decision.json').read_bytes()
    assert (tmp_path / approval['evidence']['path']).read_bytes() == original
    assert approval['evidence']['path'] != 'decision.json'
    (tmp_path / 'decision.json').write_bytes(b'new unrelated decision')
    assert store.adopt(item, approval)['reviewEventId'] == approval['eventId']


def test_missing_prepared_event_invalidates_candidate_projection(tmp_path):
    store = ProductionStore(tmp_path)
    item = candidate(store)
    prepared = store.load_prepared('a001')
    (tmp_path / 'production/events' / (prepared['eventId'] + '.json')).unlink()
    with pytest.raises(MaLiangError):
        store.project_current('falcon', item)


def test_import_reuse_cannot_overwrite_previous_artifact(tmp_path):
    store = ProductionStore(tmp_path)
    args = dict(attempt_id='old1', task={'view': 'DR'}, identity_checklist=['species'], required_acceptance=[{'id': 'species', 'method': 'human'}], provenance='historical; unknown request')
    item = store.import_artifact(png(), **args)
    with pytest.raises(CollisionError):
        store.import_artifact(png('blue'), **args)
    assert store.load_candidate('old1') == item


def test_projection_rejects_link_destination(tmp_path):
    store = ProductionStore(tmp_path)
    item = candidate(store)
    directory = tmp_path / 'production/current'
    directory.mkdir()
    link = directory / 'falcon.json'
    target = tmp_path / item['artifact']['path']
    original = target.read_bytes()
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip('symlink creation unavailable')
    with pytest.raises(MaLiangError):
        store.project_current('falcon', item)
    assert target.read_bytes() == original


def mixed_manifest():
    return [
        {'id': 'species', 'method': 'human'},
        {'id': 'mark', 'method': 'human'},
        {'id': 'style', 'method': 'human'},
        {'id': 'alpha-bounds', 'method': 'automatic'},
    ]


def mixed_candidate(store, attempt='a001'):
    return store.succeed(prepare(store, attempt, required_acceptance=mixed_manifest()), png(), delivered_at=TIME)


def automatic_result(store, item, tmp_path, status='pass', item_id='alpha-bounds'):
    data = json.dumps({'syntheticMeasurement': {'bbox': [0, 0, 2, 2]}, 'status': status}).encode()
    (tmp_path / 'measurement.json').write_bytes(data)
    artifact = {'path': 'measurement.json', 'sha256': hashlib.sha256(data).hexdigest()}
    return store.record_automatic_result(item, item_id=item_id, status=status,
                                         evaluator='synthetic alpha checker', evidence=artifact)


def mixed_review(store, item, tmp_path, style='pass', **kwargs):
    return review(store, item, tmp_path, checklist={'species': 'pass', 'mark': 'pass', 'style': style}, **kwargs)


@pytest.mark.parametrize('status', ['fail', 'pending', 'unsupported'])
def test_required_automatic_nonpass_blocks_adoption(tmp_path, status):
    store = ProductionStore(tmp_path)
    item = mixed_candidate(store)
    approval = mixed_review(store, item, tmp_path)
    result = automatic_result(store, item, tmp_path, status)
    with pytest.raises(MaLiangError):
        store.adopt(item, approval, automatic_results=[result])


@pytest.mark.parametrize('status', ['fail', 'pending', 'unsupported'])
def test_required_nonidentity_human_nonpass_blocks_adoption(tmp_path, status):
    store = ProductionStore(tmp_path)
    item = mixed_candidate(store)
    approval = mixed_review(store, item, tmp_path, status)
    result = automatic_result(store, item, tmp_path)
    with pytest.raises(MaLiangError):
        store.adopt(item, approval, automatic_results=[result])


def test_required_human_item_missing_blocks_despite_passing_technical_result(tmp_path):
    store = ProductionStore(tmp_path)
    item = mixed_candidate(store)
    result = automatic_result(store, item, tmp_path)
    approval = review(store, item, tmp_path)
    with pytest.raises(MaLiangError, match='human acceptance evidence is incomplete'):
        store.adopt(item, approval, automatic_results=[result])


def test_missing_technical_report_event_blocks_adopted_projection(tmp_path):
    store = ProductionStore(tmp_path)
    item = mixed_candidate(store)
    result = automatic_result(store, item, tmp_path)
    approval = mixed_review(store, item, tmp_path)
    adoption = store.adopt(item, approval, automatic_results=[result])
    path = store.project_current('falcon', item, adoption=adoption)
    original = path.read_bytes()
    (tmp_path / 'production/events' / (result['eventId'] + '.json')).unlink()
    with pytest.raises(MaLiangError):
        store.project_current('falcon', item, adoption=adoption)
    assert path.read_bytes() == original


def test_results_cannot_transfer_to_identical_bytes_in_another_attempt(tmp_path):
    store = ProductionStore(tmp_path)
    first = mixed_candidate(store)
    result = automatic_result(store, first, tmp_path)
    second = mixed_candidate(store, 'a002')
    assert first['artifact']['sha256'] == second['artifact']['sha256']
    approval = mixed_review(store, second, tmp_path)
    with pytest.raises(MaLiangError):
        store.adopt(second, approval, automatic_results=[result])


def test_all_required_results_allow_direct_adoption_and_validated_projection(tmp_path):
    store = ProductionStore(tmp_path)
    item = mixed_candidate(store)
    result = automatic_result(store, item, tmp_path)
    approval = mixed_review(store, item, tmp_path)
    adoption = store.adopt(item, approval, automatic_results=[result])
    assert adoption['automaticResultEventIds'] == [result['eventId']]
    assert store.load_candidate('a001') == item
    assert list((tmp_path / 'production/attempts').iterdir()) == [tmp_path / 'production/attempts/a001']
    sources = [item['eventId'], approval['eventId'], result['eventId'], adoption['eventId']]
    path = store.project_current('falcon', item, adoption=adoption, source_events=sources)
    assert json.loads(path.read_bytes())['status'] == 'adopted'
    previous = path.read_bytes()
    (tmp_path / result['evidence']['path']).write_bytes(b'tampered technical report')
    with pytest.raises(MaLiangError):
        store.project_current('falcon', item, adoption=adoption)
    assert path.read_bytes() == previous


def test_acceptance_manifest_is_frozen_and_preserved_through_derivation(tmp_path):
    store = ProductionStore(tmp_path)
    manifest = mixed_manifest()
    request = prepare(store, required_acceptance=manifest)
    manifest[0]['method'] = 'automatic'
    assert request['requiredAcceptance'] == mixed_manifest()
    item = store.succeed(request, png(), delivered_at=TIME)
    assert item['requiredAcceptance'] == mixed_manifest()
    args = dict(attempt_id='import1', task={'view': 'DR'}, identity_checklist=['species', 'mark'],
                required_acceptance=mixed_manifest(), provenance='synthetic imported image')
    imported = store.import_artifact(png(), **args)
    derived = store.derive(imported, png('blue'), attempt_id='derived1', operation='flipX', parameters={})
    assert derived['requiredAcceptance'] == imported['requiredAcceptance'] == mixed_manifest()
    result = automatic_result(store, imported, tmp_path)
    with pytest.raises(MaLiangError):
        store.adopt(derived, mixed_review(store, derived, tmp_path), automatic_results=[result])


def test_human_checklist_cannot_substitute_for_automatic_evidence(tmp_path):
    store = ProductionStore(tmp_path)
    item = mixed_candidate(store)
    with pytest.raises(MaLiangError):
        review(store, item, tmp_path, checklist={'species': 'pass', 'mark': 'pass', 'style': 'pass', 'alpha-bounds': 'pass'})
    with pytest.raises(MaLiangError):
        automatic_result(store, item, tmp_path, item_id='style')


def test_missing_human_decision_and_duplicate_results_block_adoption(tmp_path):
    store = ProductionStore(tmp_path)
    item = mixed_candidate(store)
    result = automatic_result(store, item, tmp_path)
    approval = mixed_review(store, item, tmp_path, decision='pending')
    with pytest.raises(MaLiangError):
        store.adopt(item, approval, automatic_results=[result])
    approval = mixed_review(store, item, tmp_path)
    with pytest.raises(MaLiangError):
        store.adopt(item, approval, automatic_results=[result, result])


@pytest.mark.parametrize('manifest', [[], [{'id': 'species', 'method': 'human'}],
    [{'id': 'species', 'method': 'automatic'}, {'id': 'mark', 'method': 'human'}],
    [{'id': 'species', 'method': 'human'}, {'id': 'mark', 'method': 'human'}, {'id': 'mark', 'method': 'automatic'}],
    [{'id': 'species', 'method': 'human'}, {'id': 'mark', 'method': 'unknown'}],
])
def test_invalid_or_identity_omitting_acceptance_manifest_rejected(tmp_path, manifest):
    with pytest.raises(MaLiangError):
        prepare(ProductionStore(tmp_path), required_acceptance=manifest)


def test_explicit_acceptance_manifest_is_required(tmp_path):
    store = ProductionStore(tmp_path)
    with pytest.raises(TypeError):
        store.prepare(attempt_id='no-manifest', task={'view': 'DR'}, prompt='synthetic', parameters={},
                      inputs=[], design_package_sha256=SHA, provider='offline', model='unknown',
                      requested_at=TIME, identity_checklist=['species'])
    with pytest.raises(TypeError):
        store.import_artifact(png(), attempt_id='no-manifest', task={'view': 'DR'},
                              identity_checklist=['species'], provenance='historical')


def test_identity_only_adoption_does_not_satisfy_declared_technical_acceptance(tmp_path):
    store = ProductionStore(tmp_path)
    request = prepare(store, required_acceptance=mixed_manifest())
    item = store.succeed(request, png(), delivered_at=TIME)
    approval = mixed_review(store, item, tmp_path)
    with pytest.raises(MaLiangError, match='automatic acceptance evidence is missing'):
        store.adopt(item, approval)


@pytest.mark.parametrize('change', [dict(attempt_id='../escape'), dict(design_package_sha256='wrong'), dict(model=''), dict(identity_checklist=[]), dict(kind='imported'), dict(kind='generation', edit_instruction='edit')])
def test_invalid_requests_rejected(tmp_path, change):
    with pytest.raises(MaLiangError):
        prepare(ProductionStore(tmp_path), **change)
