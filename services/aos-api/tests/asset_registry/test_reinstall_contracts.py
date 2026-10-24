"""Pure DTO tests: no conftest, database, identity, runtime or IO authority."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest
from uuid import UUID

EFFECTS = []
os.environ["AOS_DOTENV_DISABLED"] = "1"
if __name__ == "__main__":
    if not sys.flags.isolated or not sys.dont_write_bytecode or len(sys.argv) != 1:
        raise SystemExit(2)
    for name in tuple(os.environ):
        if name.startswith(("PG", "AOS_DATABASE", "AOS_TEST_")):
            os.environ.pop(name, None)

    def audit(event, args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "subprocess.Popen",
                     "os.system", "os.posix_spawn", "os.fork"}:
            EFFECTS.append(event)
            raise RuntimeError("REINSTALL_CONTRACT_EFFECT_DENIED")
        if event == "open":
            name, mode, flags = args
            if isinstance(name, (str, bytes)):
                leaf = Path(os.fsdecode(name)).name
                if leaf in {".env", ".secrets.env"} or leaf.endswith("-identity.json"):
                    EFFECTS.append("private")
                    raise RuntimeError("REINSTALL_CONTRACT_PRIVATE_DENIED")
            if (isinstance(mode, str) and any(c in mode for c in "wax+")
                    or isinstance(flags, int) and flags & (
                        os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                EFFECTS.append("write")
                raise RuntimeError("REINSTALL_CONTRACT_WRITE_DENIED")

    sys.addaudithook(audit)
    import psycopg

    def deny(*args, **kwargs):
        EFFECTS.append("database")
        raise RuntimeError("REINSTALL_CONTRACT_DB_DENIED")

    psycopg.connect = deny
    psycopg.Connection.connect = staticmethod(deny)

sys.path.insert(0, str(Path(__file__).absolute().parents[2]))
from pydantic import ValidationError
from aos_api.asset_registry.composition_contracts import CreateInstallationRequest
from aos_api.asset_registry.installation_store import command_request_hash
from aos_api.asset_registry.reinstall_contracts import ReinstallInstallationRequest, ReinstallSourceRef


SOURCE = dict(installationId=str(UUID(int=1)), terminalRevision=8, lockHash="sha256:" + "a" * 64)
TARGET = dict(compositionId=str(UUID(int=2)), lockRevision=1,
              overlayRevision="synthetic-reinstall", displayName="Synthetic reinstall")


def payload():
    return dict(source=deepcopy(SOURCE), target=deepcopy(TARGET))


class ReinstallContractsTests(unittest.TestCase):
    def test_valid_source_and_target_aliases_reuse_original_target(self):
        request = ReinstallInstallationRequest.model_validate(payload())
        self.assertIs(type(request.source), ReinstallSourceRef)
        self.assertIs(type(request.target), CreateInstallationRequest)
        self.assertEqual(request.model_dump(mode="json", by_alias=True), payload())
        self.assertEqual(request.source.terminal_revision, 8)
        self.assertEqual(request.target.lock_revision, 1)

    def test_source_uuid_hash_and_revision_are_strict(self):
        changes = [
            ("installationId", "not-a-uuid"),
            ("installationId", str(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")).upper()),
            ("installationId", str(UUID(int=1)).replace("-", "")),
            ("installationId", " " + str(UUID(int=1))),
            ("installationId", True),
            ("lockHash", "sha256:" + "A" * 64),
            ("lockHash", "sha256:" + "a" * 63),
            ("lockHash", None),
            ("terminalRevision", True),
            ("terminalRevision", 8.0),
            ("terminalRevision", "8"),
            ("terminalRevision", 0),
            ("terminalRevision", -1),
        ]
        for field, value in changes:
            with self.subTest(field=field, shape=type(value).__name__), self.assertRaises(ValidationError):
                ReinstallSourceRef.model_validate(dict(SOURCE, **{field: value}))

    def test_missing_extra_and_authority_fields_are_forbidden(self):
        for place in ("root", "source", "target"):
            for field in ("orgId", "projectId", "actor", "roles", "secretRef", "canExecute"):
                value = payload()
                parent = value if place == "root" else value[place]
                parent[field] = "synthetic-untrusted-field"
                with self.subTest(place=place, field=field), self.assertRaises(ValidationError):
                    ReinstallInstallationRequest.model_validate(value)
        for place, fields in (("root", ("source", "target")),
                              ("source", tuple(SOURCE)), ("target", tuple(TARGET))):
            for field in fields:
                value = payload()
                del (value if place == "root" else value[place])[field]
                with self.subTest(missing=field), self.assertRaises(ValidationError):
                    ReinstallInstallationRequest.model_validate(value)
        for field in ("source", "target"):
            for value in (None, True, [], object()):
                with self.subTest(field=field), self.assertRaises(ValidationError):
                    ReinstallInstallationRequest.model_validate(dict(payload(), **{field: value}))

    def test_target_uses_original_validation_without_a_second_schema(self):
        for field, value in (
            ("compositionId", "not-a-uuid"), ("lockRevision", True), ("lockRevision", 0),
            ("lockRevision", "1"), ("displayName", " padded "), ("displayName", "bad\x00name"),
            ("overlayRevision", ""), ("overlayRevision", "x" * 161),
        ):
            value_dict = dict(TARGET, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValidationError):
                CreateInstallationRequest.model_validate(value_dict)
            with self.subTest(nested_field=field), self.assertRaises(ValidationError):
                ReinstallInstallationRequest.model_validate(dict(source=SOURCE, target=value_dict))

    def test_constructed_or_mutated_models_are_revalidated(self):
        source = ReinstallSourceRef.model_construct(installation_id="invalid",
                                                   terminal_revision=8, lock_hash=SOURCE["lockHash"])
        with self.assertRaises(ValidationError):
            ReinstallInstallationRequest.model_validate(dict(source=source, target=TARGET))
        with self.assertRaises(ValidationError):
            ReinstallSourceRef.model_validate(source)
        target = CreateInstallationRequest.model_validate(TARGET)
        object.__setattr__(target, "lock_revision", -1)
        with self.assertRaises(ValidationError):
            ReinstallInstallationRequest.model_validate(dict(source=SOURCE, target=target))
        outer = ReinstallInstallationRequest.model_construct(
            source=ReinstallSourceRef.model_validate(SOURCE), target=target)
        with self.assertRaises(ValidationError):
            ReinstallInstallationRequest.model_validate(outer)

    def test_subclass_overrides_are_not_evaluated_as_trusted_models(self):
        calls = []

        class SourceOverride(ReinstallSourceRef):
            def model_dump(self, *args, **kwargs):
                calls.append("source")
                raise AssertionError("untrusted override")

        class TargetOverride(CreateInstallationRequest):
            def model_dump(self, *args, **kwargs):
                calls.append("target")
                raise AssertionError("untrusted override")

        for field, value in (
            ("source", SourceOverride.model_validate(SOURCE)),
            ("target", TargetOverride.model_validate(TARGET)),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ReinstallInstallationRequest.model_validate(dict(payload(), **{field: value}))
        self.assertEqual(calls, [])

    def test_copies_isolate_caller_dicts_and_existing_models(self):
        raw = payload()
        source = ReinstallSourceRef.model_validate(SOURCE)
        target = CreateInstallationRequest.model_validate(TARGET)
        request = ReinstallInstallationRequest.model_validate(dict(source=source, target=target))
        self.assertIsNot(request.source, source)
        self.assertIsNot(request.target, target)
        request.target.display_name = "Changed only in new request"
        request.source.terminal_revision = 9
        self.assertEqual(target.display_name, TARGET["displayName"])
        self.assertEqual(source.terminal_revision, 8)
        copied = ReinstallInstallationRequest.model_validate(raw)
        raw["target"]["displayName"] = "Changed only in caller"
        self.assertEqual(copied.target.display_name, TARGET["displayName"])

        for obj, field, value in (
            (request.source, "terminal_revision", 0),
            (request.source, "installation_id", "invalid"),
            (request.target, "lock_revision", True),
            (request, "source", ReinstallSourceRef.model_construct(
                installation_id=SOURCE["installationId"], terminal_revision=0, lock_hash=SOURCE["lockHash"])),
            (request, "target", True),
            (request, "actor", "synthetic-untrusted-actor"),
        ):
            before = request.model_dump(mode="json", by_alias=True)
            with self.subTest(assignment=field), self.assertRaises(ValidationError):
                setattr(obj, field, value)
            self.assertEqual(request.model_dump(mode="json", by_alias=True), before)


    def test_legacy_four_field_wire_and_hash_are_unchanged(self):
        original = CreateInstallationRequest.model_validate(TARGET)
        body = original.model_dump(mode="json", by_alias=True)
        self.assertEqual(body, TARGET)
        self.assertEqual(set(CreateInstallationRequest.model_fields), {
            "composition_id", "lock_revision", "overlay_revision", "display_name"})
        def digest(value):
            return command_request_hash(subject="synthetic-contract-author",
                                        path_params={}, body=value, if_match=None)
        request = ReinstallInstallationRequest.model_validate(payload())
        self.assertEqual(digest(body), digest(request.target.model_dump(mode="json", by_alias=True)))
        self.assertNotEqual(digest(body), digest(dict(body, reinstallOrigin=None)))

    def test_schema_has_no_execution_or_authority_surface(self):
        self.assertEqual(set(ReinstallSourceRef.model_fields), {
            "installation_id", "terminal_revision", "lock_hash"})
        self.assertEqual(set(ReinstallInstallationRequest.model_fields), {"source", "target"})
        schema = ReinstallInstallationRequest.model_json_schema(by_alias=True)
        self.assertIs(schema["additionalProperties"], False)
        self.assertIs(schema["$defs"]["ReinstallSourceRef"]["additionalProperties"], False)
        self.assertIs(schema["$defs"]["CreateInstallationRequest"]["additionalProperties"], False)
        self.assertEqual(EFFECTS, [])


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReinstallContractsTests))
    print("EXTERNAL_OR_PRIVATE_ATTEMPTS", len(EFFECTS))
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun == 9
                     and not result.skipped and not EFFECTS else 1)
