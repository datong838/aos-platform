"""Pure command/metadata counterexamples; never use an actual Docker engine."""
import json
import subprocess
from copy import deepcopy
from types import SimpleNamespace

import pytest
import owned_fixture_resources as module

BASE = 'sha256:' + '1' * 64
LAYERS = ('sha256:' + '2' * 64,)
NAME = 'ar1-registry-' + 'a' * 32
REF = '127.0.0.1:18433/aos-test@sha256:' + 'c' * 64


class Engine:
    def __init__(self):
        self.images = {BASE: {'Id': BASE, 'Config': {'Volumes': None, 'Labels': {}},
                              'RootFS': {'Layers': list(LAYERS)}, 'RepoTags': [], 'RepoDigests': []}}
        self.containers, self.references = {}, {}
        self.calls, self.removed = [], []
        self.unknown_run = self.unknown_remove = self.failed_remove = False
        self.n = 3

    def run(self, command, **kwargs):
        self.calls.append(command)
        assert command[:3] == ['docker', '--context', 'colima-aos-extension']
        args = command[3:]
        value, code, error = '', 0, ''
        if args[:2] == ['image', 'ls']:
            value = '\n'.join(self.images)
        elif args[:2] == ['container', 'ls']:
            image = args[args.index('--filter') + 1].removeprefix('ancestor=')
            value = '\n'.join(c['Id'] for c in self.containers.values() if c['Image'] == image)
        elif args[0] == 'build':
            labels = dict(args[i + 1].split('=', 1) for i, a in enumerate(args) if a == '--label')
            self.n += 1
            image = 'sha256:' + f'{self.n:064x}'
            self.images[image] = {'Id': image, 'Config': {'Labels': labels, 'Volumes': None},
                'RootFS': {'Layers': [*LAYERS, 'sha256:' + 'e' * 64]}, 'RepoTags': [], 'RepoDigests': []}
            value = image
        elif args[0] == 'run':
            name = args[args.index('--name') + 1]
            labels = dict(args[i + 1].split('=', 1) for i, a in enumerate(args) if a == '--label')
            self.n += 1
            identifier = f'{self.n:064x}'
            self.containers[name] = {'Id': identifier, 'Name': '/' + name,
                'Image': args[-1], 'Config': {'Labels': labels}, 'Mounts': []}
            if self.unknown_run:
                raise subprocess.TimeoutExpired(command, 15)
            value = identifier
        elif len(args) >= 2 and args[1] == 'inspect':
            kind, target = args[0], args[-1]
            if kind == 'image':
                item = self.images.get(self.references.get(target, BASE if target == 'python:3.11-alpine' else target))
            else:
                item = self.containers.get(target) or next((c for c in self.containers.values() if c['Id'] == target), None)
            if item is None:
                code, error = 1, 'Error: no such ' + kind
            else:
                value = json.dumps([item])
        elif len(args) >= 2 and args[1] == 'rm':
            kind, target = args[0], args[-1]
            if self.failed_remove:
                return SimpleNamespace(returncode=1, stdout='', stderr='synthetic refusal')
            self.removed.append((kind, target))
            if kind == 'container':
                self.containers = {k: v for k, v in self.containers.items() if v['Id'] != target}
            elif target in self.references:
                image = self.images[self.references.pop(target)]
                image['RepoDigests'].remove(target)
            else:
                self.images.pop(target, None)
            if self.unknown_remove:
                raise subprocess.TimeoutExpired(command, 15)
        else:
            raise AssertionError('unplanned fake command')
        return SimpleNamespace(returncode=code, stdout=value, stderr=error)


@pytest.fixture
def engine(monkeypatch):
    engine = Engine()
    monkeypatch.setattr(module.subprocess, 'run', engine.run)
    return engine


def scope(events=None, **kwargs):
    return module.owned_fixture_scope('qyh-test-fixture', 'colima-aos-extension', BASE, LAYERS,
                                      (events if events is not None else []).append, **kwargs)


def test_scope_is_explicit_no_effect_and_resets_on_error(engine):
    assert module.current_scope('colima-aos-extension') is None
    with pytest.raises(ValueError, match='body'):
        with scope() as current:
            assert module.current_scope('colima-aos-extension') is current
            with pytest.raises(ValueError):
                module.current_scope('desktop-linux')
            with pytest.raises(ValueError):
                with scope():
                    pass
            raise ValueError('body')
    assert module.current_scope('colima-aos-extension') is None
    assert engine.calls == []


@pytest.mark.parametrize('owner,context,base,layers', [
    ('bad owner', 'colima-aos-extension', BASE, LAYERS),
    ('valid', 'desktop-linux', BASE, LAYERS), ('valid', 'colima-aos-extension', 'mutable', LAYERS),
    ('valid', 'colima-aos-extension', BASE, ()),
])
def test_invalid_scope_never_calls_engine(engine, owner, context, base, layers):
    with pytest.raises(ValueError):
        with module.owned_fixture_scope(owner, context, base, layers, [].append):
            pass
    assert engine.calls == []


def test_fresh_builds_unique_labels_and_only_new_images_removed(engine):
    events = []
    with scope(events) as current:
        a, b = current.build('/tmp/test-a'), current.build('/tmp/test-b')
        assert a != b
        la, lb = engine.images[a]['Config']['Labels'], engine.images[b]['Config']['Labels']
        assert la['aos.test.fixture.owner'] == lb['aos.test.fixture.owner'] == 'qyh-test-fixture'
        assert la['aos.test.fixture.nonce'] != lb['aos.test.fixture.nonce']
        assert events[0]['event'] == 'build-intent'
    assert set(engine.images) == {BASE}
    assert all(target != BASE for _, target in engine.removed)
    with pytest.raises(ValueError):
        current.build('/tmp/closed')


def test_base_drift_refuses_before_build(engine):
    engine.images[BASE]['RootFS']['Layers'] = ['sha256:' + 'f' * 64]
    with pytest.raises(ValueError):
        with scope() as current:
            current.build('/tmp/test')
    assert not any(c[3] == 'build' for c in engine.calls)


def test_recorder_failure_blocks_effect(engine):
    def fail(event):
        raise RuntimeError('journal unavailable')
    with pytest.raises(RuntimeError):
        with module.owned_fixture_scope('qyh-test-fixture', 'colima-aos-extension', BASE, LAYERS, fail) as current:
            current.build('/tmp/test')
    assert not any(c[3] == 'build' for c in engine.calls)


@pytest.mark.parametrize('field', ['owner', 'nonce', 'tag'])
def test_changed_image_identity_or_foreign_tag_never_removed(engine, field):
    with pytest.raises(RuntimeError):
        with scope() as current:
            image = current.build('/tmp/test')
            if field == 'tag':
                engine.images[image]['RepoTags'] = ['foreign:keep']
            else:
                engine.images[image]['Config']['Labels']['aos.test.fixture.' + field] = 'foreign'
    assert engine.removed == []
    assert image in engine.images


def test_registry_ref_cleanup_order_and_unrelated_images_preserved(engine):
    with scope() as current:
        backend, helper = current.build('/tmp/backend'), current.build('/tmp/helper')
        identifier = current.create_registry(NAME, helper)
        current.before_pull(REF, backend)
        engine.references[REF] = backend
        engine.images[backend]['RepoDigests'] = [REF]
        current.after_pull(REF, backend)
        current.cleanup_registry(NAME, REF, helper)
        assert engine.removed[:3] == [('container', identifier), ('image', REF), ('image', helper)]
        assert BASE in engine.images and backend in engine.images
    assert set(engine.images) == {BASE}


def test_existing_registry_name_is_not_touched(engine):
    foreign = {'Id': 'f' * 64, 'Name': '/' + NAME, 'Config': {'Labels': {}}, 'Image': BASE, 'Mounts': []}
    engine.containers[NAME] = deepcopy(foreign)
    with pytest.raises(ValueError):
        with scope() as current:
            helper = current.build('/tmp/helper')
            current.create_registry(NAME, helper)
    assert engine.containers[NAME] == foreign
    assert not any(kind == 'container' for kind, _ in engine.removed)


@pytest.mark.parametrize('change', ['id', 'name', 'owner', 'mount'])
def test_wrong_registry_identity_is_not_removed(engine, change):
    with pytest.raises(RuntimeError):
        with scope() as current:
            helper = current.build('/tmp/helper')
            current.create_registry(NAME, helper)
            item = engine.containers[NAME]
            if change == 'id': item['Id'] = 'f' * 64
            if change == 'name': item['Name'] = '/other'
            if change == 'owner': item['Config']['Labels']['aos.test.fixture.owner'] = 'other'
            if change == 'mount': item['Mounts'] = [{'Name': 'foreign-volume'}]
    assert not any(kind == 'container' for kind, _ in engine.removed)


def test_unknown_create_is_not_replayed_and_owned_readback_can_cleanup(engine):
    engine.unknown_run = True
    with pytest.raises(subprocess.TimeoutExpired):
        with scope() as current:
            helper = current.build('/tmp/helper')
            current.create_registry(NAME, helper)
    assert sum(c[3] == 'run' for c in engine.calls) == 1
    assert engine.containers == {}
    assert set(engine.images) == {BASE}


def test_unknown_remove_confirmed_absent_is_not_repeated(engine):
    engine.unknown_remove = True
    with scope() as current:
        image = current.build('/tmp/backend')
    assert engine.removed == [('image', image)]


def test_body_and_cleanup_failures_both_preserved(engine):
    with pytest.raises(BaseExceptionGroup) as caught:
        with scope() as current:
            current.build('/tmp/backend')
            engine.failed_remove = True
            raise LookupError('original body')
    assert isinstance(caught.value.exceptions[0], LookupError)
    assert isinstance(caught.value.exceptions[1], RuntimeError)
    assert module.current_scope('colima-aos-extension') is None


def test_existing_ref_and_wrong_ref_binding_refuse_without_removal(engine):
    engine.references[REF] = BASE
    with pytest.raises(ValueError):
        with scope() as current:
            backend = current.build('/tmp/backend')
            current.before_pull(REF, backend)
    assert engine.references[REF] == BASE
    assert ('image', REF) not in engine.removed


def test_failed_removal_is_not_resent_by_outer_scope(engine):
    with pytest.raises(RuntimeError):
        with scope() as current:
            helper = current.build('/tmp/helper')
            engine.failed_remove = True
            with pytest.raises(RuntimeError):
                current.cleanup_registry(NAME, REF, helper)
    removes = [c for c in engine.calls if c[3:5] == ['image', 'rm']]
    assert len(removes) == 1


def test_strict_registry_rejects_foreign_backend_before_export(engine, tmp_path):
    from offline_registry import cached_registry_image
    with scope():
        with pytest.raises(ValueError):
            with cached_registry_image(tmp_path / 'registry', BASE, 'colima-aos-extension'):
                pass
    assert not (tmp_path / 'registry').exists()
    assert not any(c[3:5] == ['image', 'save'] for c in engine.calls)


def test_original_backend_helper_uses_explicit_scope_without_changing_return(engine, tmp_path, monkeypatch):
    from test_persistent_supervisor import build_session_image
    with scope() as current:
        calls = []
        monkeypatch.setattr(current, 'build', lambda path: calls.append(path) or 'sha256:' + 'a' * 64)
        image, claims = build_session_image(tmp_path)
        assert calls == [tmp_path]
        assert image == 'sha256:' + 'a' * 64
        assert claims['contributions'][0]['operationId'] == 'example_read'


def test_strict_registry_full_helper_pipeline_is_fake_only(engine, tmp_path, monkeypatch):
    import io
    import tarfile
    import offline_registry
    original_run = engine.run
    backend_holder = {}

    def run(command, **kwargs):
        if command[:5] == ['docker', '--context', 'colima-aos-extension', 'image', 'save']:
            engine.calls.append(command)
            members = {'manifest.json': json.dumps([{'Config': 'config.json', 'Layers': ['layer.tar']}]).encode(),
                       'config.json': b'{"synthetic":true}', 'layer.tar': b'synthetic layer'}
            with tarfile.open(command[6], 'w') as archive:
                for name, value in members.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(value)
                    archive.addfile(info, io.BytesIO(value))
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if command[:2] == ['docker', '--config']:
            engine.calls.append(command)
            assert command[3:6] == ['--host', 'unix:///tmp/test-only-engine.sock', 'pull']
            ref = command[-1]
            backend = backend_holder['id']
            engine.references[ref] = backend
            engine.images[backend]['RepoDigests'].append(ref)
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        return original_run(command, **kwargs)

    monkeypatch.setattr(module.subprocess, 'run', run)
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *a, **k: '"unix:///tmp/test-only-engine.sock"')
    response = SimpleNamespace(status=200)
    from contextlib import nullcontext
    monkeypatch.setattr(offline_registry.urllib.request, 'urlopen', lambda *a, **k: nullcontext(response))
    with scope() as current:
        backend_holder['id'] = current.build('/tmp/backend')
        with offline_registry.cached_registry_image(tmp_path / 'registry', backend_holder['id'], 'colima-aos-extension') as result:
            assert len(result) == 2 and all(value.startswith('sha256:') for value in result)
            assert len(engine.containers) == 1
        assert not engine.containers and not engine.references
    assert set(engine.images) == {BASE}


def test_cached_build_cannot_claim_or_remove_an_existing_image(engine, monkeypatch):
    original_run = engine.run
    def run(command, **kwargs):
        if command[3] == 'build':
            engine.calls.append(command)
            return SimpleNamespace(returncode=0, stdout=BASE, stderr='')
        return original_run(command, **kwargs)
    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(ValueError):
        with scope() as current:
            current.build('/tmp/cache-collision')
    assert engine.removed == [] and set(engine.images) == {BASE}


def test_base_changes_during_build_only_owned_new_image_can_be_cleaned(engine, monkeypatch):
    original_run = engine.run
    def run(command, **kwargs):
        result = original_run(command, **kwargs)
        if command[3] == 'build':
            engine.images[BASE]['RootFS']['Layers'] = ['sha256:' + 'f' * 64]
        return result
    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(ValueError):
        with scope() as current:
            current.build('/tmp/base-drift')
    assert set(engine.images) == {BASE} and all(target != BASE for _, target in engine.removed)


def test_renamed_unknown_removal_is_not_falsely_reported_absent(engine, monkeypatch):
    original_run = engine.run
    def run(command, **kwargs):
        if command[3:5] == ['container', 'rm']:
            engine.calls.append(command)
            item = engine.containers.pop(NAME)
            item['Name'] = '/renamed'
            engine.containers['renamed'] = item
            raise subprocess.TimeoutExpired(command, 15)
        return original_run(command, **kwargs)
    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(RuntimeError):
        with scope() as current:
            helper = current.build('/tmp/helper')
            current.create_registry(NAME, helper)
    assert 'renamed' in engine.containers
    assert sum(c[3:5] == ['container', 'rm'] for c in engine.calls) == 1


def test_image_used_by_foreign_container_is_not_deleted(engine):
    with pytest.raises(RuntimeError):
        with scope() as current:
            image = current.build('/tmp/backend')
            engine.containers['foreign'] = {'Id': 'f' * 64, 'Image': image}
    assert image in engine.images and ('image', image) not in engine.removed
