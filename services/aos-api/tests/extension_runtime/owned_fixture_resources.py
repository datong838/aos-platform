"""Opt-in test fixture ownership, not runtime or business authorization."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import re
import subprocess
import uuid

_CURRENT = ContextVar('owned_test_fixture_scope', default=None)
OWNER_LABEL = 'aos.test.fixture.owner'
NONCE_LABEL = 'aos.test.fixture.nonce'
_DIGEST = re.compile(r'sha256:[0-9a-f]{64}')
_CONTAINER = re.compile(r'[0-9a-f]{64}')
_REF = re.compile(r'127\.0\.0\.1:18433/aos-test@sha256:[0-9a-f]{64}')


def finish_cleanup(callback, error=None):
    try:
        callback()
    except BaseException as cleanup_error:
        if error is not None:
            raise BaseExceptionGroup('fixture body and cleanup failed', [error, cleanup_error]) from None
        raise


def current_scope(context):
    scope = _CURRENT.get()
    if scope is not None and (scope.closed or scope.context != context):
        raise ValueError('fixture context differs')
    return scope


@contextmanager
def owned_fixture_scope(owner, context, base_image_id, base_layers, record):
    if _CURRENT.get() is not None:
        raise ValueError('nested fixture scope forbidden')
    scope = FixtureScope(owner, context, base_image_id, base_layers, record)
    token, error = _CURRENT.set(scope), None
    try:
        yield scope
    except BaseException as exc:
        error = exc
        raise
    finally:
        _CURRENT.reset(token)
        try:
            finish_cleanup(scope.cleanup_all, error)
        finally:
            scope.closed = True


class FixtureScope:
    def __init__(self, owner, context, base_image_id, base_layers, record):
        if (type(owner) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', owner) is None
                or context != 'colima-aos-extension' or type(base_image_id) is not str
                or _DIGEST.fullmatch(base_image_id) is None or not isinstance(base_layers, (tuple, list))
                or not base_layers or not all(type(x) is str and _DIGEST.fullmatch(x) for x in base_layers)
                or not callable(record)):
            raise ValueError('invalid explicit fixture scope')
        self.owner, self.context, self.base = owner, context, base_image_id
        self.layers, self.record = tuple(base_layers), record
        self.images, self.containers, self.references = {}, {}, {}
        self.removal_attempts = set()
        self.closed = False

    def _open(self):
        if self.closed:
            raise ValueError('fixture scope closed')

    def _emit(self, event, **fields):
        self.record(dict(event=event, owner=self.owner, context=self.context, **fields))

    def _run(self, *args, check=True, timeout=15):
        self._open()
        result = subprocess.run(['docker', '--context', self.context, *args],
                                capture_output=True, text=True, timeout=timeout)
        if check and result.returncode != 0:
            raise RuntimeError('fixture command failed; reconcile without resend')
        return result

    def _inspect(self, kind, target):
        result = self._run(kind, 'inspect', target, check=False)
        if result.returncode != 0:
            if 'no such' in result.stderr.lower():
                return None
            raise RuntimeError('fixture observation unavailable')
        items = json.loads(result.stdout)
        if type(items) is not list or len(items) != 1 or type(items[0]) is not dict:
            raise ValueError('fixture observation shape differs')
        return items[0]

    def _base_current(self):
        item = self._inspect('image', 'python:3.11-alpine')
        if (item is None or item.get('Id') != self.base or item.get('Config', {}).get('Volumes')
                or tuple(item.get('RootFS', {}).get('Layers', [])) != self.layers):
            raise ValueError('fixture base image differs')

    def _image(self, image):
        if image not in self.images or image == self.base:
            raise ValueError('image not owned by this fixture')
        item = self._inspect('image', image)
        self._image_identity(item, image, self.images[image])
        return item

    def require_image(self, image):
        """Reject a foreign backend before the registry exports any image bytes."""
        self._image(image)

    def _image_identity(self, item, image, nonce):
        labels = (item or {}).get('Config', {}).get('Labels') or {}
        if (item is None or item.get('Id') != image or labels.get(OWNER_LABEL) != self.owner
                or labels.get(NONCE_LABEL) != nonce or item.get('Config', {}).get('Volumes')):
            raise ValueError('fixture image identity differs')

    def build(self, directory):
        self._base_current()
        existing = set(self._run('image', 'ls', '--no-trunc', '--format', '{{.ID}}').stdout.split())
        if not all(_DIGEST.fullmatch(x) for x in existing):
            raise ValueError('fixture image inventory differs')
        nonce = uuid.uuid4().hex
        self._emit('build-intent', nonce=nonce)
        image = self._run('build', '--network=none', '--pull=false', '--label', OWNER_LABEL + '=' + self.owner,
                          '--label', NONCE_LABEL + '=' + nonce, '-q', str(directory), timeout=60).stdout.strip()
        if _DIGEST.fullmatch(image) is None or image == self.base or image in existing:
            raise ValueError('fixture build is not a new image')
        item = self._inspect('image', image)
        self._image_identity(item, image, nonce)
        self.images[image] = nonce
        if tuple(item.get('RootFS', {}).get('Layers', []))[:len(self.layers)] != self.layers:
            raise ValueError('fixture build base layers differ')
        self._base_current()
        self._emit('build-observed', image=image, nonce=nonce)
        return image

    def create_registry(self, name, helper):
        if type(name) is not str or re.fullmatch(r'ar1-registry-[0-9a-f]{32}', name) is None:
            raise ValueError('invalid registry fixture name')
        self._image(helper)
        if name in self.containers or self._inspect('container', name) is not None:
            raise ValueError('registry name already exists')
        nonce = uuid.uuid4().hex
        self._emit('registry-intent', name=name, nonce=nonce, image=helper)
        entry = self.containers[name] = dict(identifier=None, nonce=nonce, image=helper)
        identifier = self._run('run', '-d', '--name', name, '--label', OWNER_LABEL + '=' + self.owner,
            '--label', NONCE_LABEL + '=' + nonce, '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--memory=256m', '--pids-limit=32',
            '-p', '127.0.0.1:18433:5000', helper).stdout.strip()
        if _CONTAINER.fullmatch(identifier) is None:
            raise ValueError('registry container result differs')
        entry['identifier'] = identifier
        self._container_identity(self._inspect('container', name), name, entry)
        self._emit('registry-observed', name=name, identifier=identifier)
        return identifier

    def _container_identity(self, item, name, entry):
        labels = (item or {}).get('Config', {}).get('Labels') or {}
        if (item is None or type(item.get('Id')) is not str or _CONTAINER.fullmatch(item['Id']) is None
                or (entry['identifier'] is not None and item['Id'] != entry['identifier'])
                or item.get('Name') != '/' + name or item.get('Image') != entry['image']
                or labels.get(OWNER_LABEL) != self.owner or labels.get(NONCE_LABEL) != entry['nonce']
                or item.get('Mounts') != []):
            raise ValueError('registry container identity differs')

    def before_pull(self, ref, image):
        if type(ref) is not str or _REF.fullmatch(ref) is None:
            raise ValueError('invalid local fixture reference')
        self._image(image)
        if ref in self.references or self._inspect('image', ref) is not None:
            raise ValueError('fixture reference already exists')
        self._emit('pull-intent', reference=ref, image=image)
        self.references[ref] = image

    def after_pull(self, ref, image):
        if self.references.get(ref) != image:
            raise ValueError('fixture pull not registered')
        self._image_identity(self._inspect('image', ref), image, self.images[image])
        self._emit('pull-observed', reference=ref, image=image)

    def _remove(self, kind, target):
        item = self._inspect(kind, target)
        if item is None:
            return
        identifier = target
        if kind == 'container':
            self._container_identity(item, target, self.containers[target])
            identifier = item['Id']
        else:
            image = self.references.get(target, target)
            self._image_identity(item, image, self.images[image])
            if image == self.base or (target == image and (item.get('RepoTags') or item.get('RepoDigests'))):
                raise ValueError('fixture image has foreign references')
            if target == image and self._run('container', 'ls', '-a', '--filter',
                    'ancestor=' + image, '--format', '{{.ID}}').stdout.strip():
                raise ValueError('fixture image is still referenced by a container')
        attempt = (kind, identifier)
        if attempt in self.removal_attempts:
            raise RuntimeError('fixture removal already attempted; readback only')
        self._emit('cleanup-intent', kind=kind, target=target, identifier=identifier)
        self.removal_attempts.add(attempt)
        try:
            self._run(kind, 'rm', *(['-f'] if kind == 'container' else []), identifier)
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            pass  # Never resend; the independent observation below is decisive.
        if self._inspect(kind, target) is not None or (
                kind == 'container' and self._inspect(kind, identifier) is not None):
            raise RuntimeError('fixture cleanup not confirmed')
        self._emit('cleanup-absent', kind=kind, target=target)

    def _cleanup(self, targets):
        failures = []
        for kind, target in targets:
            try:
                self._remove(kind, target)
            except Exception as exc:
                failures.append(exc)
        if failures:
            raise RuntimeError('owned fixture cleanup not confirmed') from failures[0]

    def cleanup_registry(self, name, ref, helper, error=None):
        if helper not in self.images:
            raise ValueError('registry helper not owned')
        targets = []
        if name in self.containers:
            if self.containers[name]['image'] != helper:
                raise ValueError('registry helper binding differs')
            targets.append(('container', name))
        if ref in self.references:
            targets.append(('image', ref))
        targets.append(('image', helper))
        finish_cleanup(lambda: self._cleanup(targets), error)

    def cleanup_all(self):
        self._open()
        self._cleanup([*[("container", x) for x in self.containers],
                       *[("image", x) for x in self.references],
                       *[("image", x) for x in reversed(self.images)]])
