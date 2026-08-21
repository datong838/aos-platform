"""228-W0-W2: deterministic router manifest and runtime equivalence gates."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "services" / "aos-api"
MANIFEST_PATH = API_ROOT / "aos_api" / "routers" / "domain_manifest.json"
AGGREGATE_PATH = API_ROOT / "aos_api" / "routers" / "domain_aggregates.py"
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_domain_aggregates.py"
MAIN_PATH = API_ROOT / "aos_api" / "main.py"

DOMAIN_ORDER = (
    "infra",
    "admin",
    "system",
    "agent",
    "workshop",
    "ontology",
    "aip",
    "data",
    "model",
    "apollo",
)
DOMAIN_COUNTS = {
    "infra": 24,
    "admin": 8,
    "system": 4,
    "agent": 3,
    "workshop": 116,
    "ontology": 72,
    "aip": 84,
    "data": 200,
    "model": 15,
    "apollo": 9,
}
EXPECTED_DUPLICATES = [
    ["/v1/builds", "GET", 2],
    ["/v1/datasets", "GET", 2],
    ["/v1/ontology/branches", "GET", 2],
    ["/v1/ontology/branches", "POST", 2],
    ["/v1/ontology/graph-health", "GET", 2],
    ["/v1/ontology/object-types", "GET", 2],
    ["/v1/pipelines", "GET", 2],
    ["/v1/pipelines", "POST", 2],
    ["/v1/schedules", "GET", 2],
    ["/v1/schedules", "POST", 2],
]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_domain_aggregates", GENERATOR_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assigned_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


RUNTIME_PROBE = r"""
import asyncio
import collections
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import types

api_package = Path(os.environ["AOS_ROUTER_API_PACKAGE"])
package = types.ModuleType("aos_api")
package.__path__ = [str(api_package)]
package.__package__ = "aos_api"
sys.modules["aos_api"] = package

# Prefer W1's declared dependencies. The fallback only isolates this route
# inventory probe when running before W1 is merged; migration behavior has its
# own test suite and is never reported as validated by this stub.
try:
    import alembic.config  # noqa: F401
except (ImportError, ModuleNotFoundError):
    alembic = types.ModuleType("alembic")
    alembic.__path__ = []
    alembic_config = types.ModuleType("alembic.config")
    alembic_config.Config = type("Config", (), {})
    alembic_command = types.ModuleType("alembic.command")
    sys.modules.update({
        "alembic": alembic,
        "alembic.config": alembic_config,
        "alembic.command": alembic_command,
    })

try:
    import sqlalchemy  # noqa: F401
except (ImportError, ModuleNotFoundError):
    sqlalchemy = types.ModuleType("sqlalchemy")
    sqlalchemy.create_engine = lambda *_args, **_kwargs: None
    sqlalchemy.inspect = lambda *_args, **_kwargs: None
    sqlalchemy_engine = types.ModuleType("sqlalchemy.engine")
    sqlalchemy_engine.Engine = type("Engine", (), {})
    sqlalchemy_reflection = types.ModuleType("sqlalchemy.engine.reflection")
    sqlalchemy_reflection.Inspector = type("Inspector", (), {})
    sys.modules.update({
        "sqlalchemy": sqlalchemy,
        "sqlalchemy.engine": sqlalchemy_engine,
        "sqlalchemy.engine.reflection": sqlalchemy_reflection,
    })

kv_store = importlib.import_module("aos_api.aip_kv_store")
kv_store.get_payload = lambda _key: None
main = importlib.import_module("aos_api.main")
app = main.app

rows = []
critical_paths = {
    "/v1/health",
    "/v1/modules",
    "/v1/ontology/object-types",
    "/v1/aip/agents",
    "/v1/aip/logic/graphs/{graph_id}/dry-run",
    "/v1/pipeline-builder",
    "/api/ontology-geos/",
    "/api/multi-spoke-monitors/",
    "/v1/apollo/ferry/status",
}
def iter_effective_routes(routes):
    # Flatten both eager FastAPI routes and 0.141+ lazy included routers.
    for route in routes:
        effective_candidates = getattr(route, "effective_candidates", None)
        if callable(effective_candidates):
            yield from iter_effective_routes(effective_candidates())
        else:
            yield route


for route in iter_effective_routes(app.routes):
    for method in sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}):
        rows.append((
            route.path,
            method,
            route.name,
            list(getattr(route, "tags", None) or ()),
        ))
pairs = collections.Counter((path, method) for path, method, _name, _tags in rows)
schema = app.openapi()

async def probe_lifespan_boundaries():
    init_calls = []
    main.run_migrations = lambda: types.SimpleNamespace(value="managed")
    main.init_schema = lambda: init_calls.append("called")
    async with main.lifespan(app):
        pass

    def fail_migration():
        raise RuntimeError("migration-gate-probe")

    main.run_migrations = fail_migration
    propagated = False
    try:
        async with main.lifespan(app):
            pass
    except RuntimeError as exc:
        propagated = str(exc) == "migration-gate-probe"
    return not init_calls, propagated

managed_skipped_bootstrap, migration_failure_propagated = asyncio.run(
    probe_lifespan_boundaries()
)
result = {
    "count": len(rows),
    "sha256": hashlib.sha256(
        json.dumps(rows, separators=(",", ":")).encode()
    ).hexdigest(),
    "openapi_paths": len(schema["paths"]),
    "duplicates": sorted(
        [[path, method, count] for (path, method), count in pairs.items() if count > 1]
    ),
    "missing_critical": sorted(critical_paths - {row[0] for row in rows}),
    "managed_skipped_bootstrap": managed_skipped_bootstrap,
    "migration_failure_propagated": migration_failure_propagated,
}
Path(os.environ["AOS_ROUTER_PROBE_OUTPUT"]).write_text(json.dumps(result))
"""


class RouterManifestStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generator = _load_generator()
        cls.routers = cls.generator.load_manifest(MANIFEST_PATH)

    def test_manifest_count_order_domains_and_unique_keys(self) -> None:
        self.assertEqual(535, len(self.routers))
        self.assertEqual(list(range(535)), [entry["order"] for entry in self.routers])
        self.assertEqual(
            DOMAIN_COUNTS,
            {
                domain: sum(entry["domain"] == domain for entry in self.routers)
                for domain in DOMAIN_ORDER
            },
        )
        keys = {(entry["module"], entry["attribute"]) for entry in self.routers}
        self.assertEqual(535, len(keys))

    def test_main_exposes_control_plane_etag_to_browser_clients(self) -> None:
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        lists = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.keyword)
            and node.arg == "expose_headers"
            and isinstance(node.value, ast.List)
        ]
        self.assertEqual(1, len(lists))
        self.assertEqual(
            ["X-Trace-Id", "ETag"],
            [item.value for item in lists[0].elts if isinstance(item, ast.Constant)],
        )

    def test_manifest_validation_rejects_order_gaps_and_duplicate_keys(self) -> None:
        samples = []
        order_gap = [dict(entry) for entry in self.routers[:2]]
        order_gap[1]["order"] = 7
        samples.append(order_gap)
        duplicate = [dict(entry) for entry in self.routers[:2]]
        duplicate[1]["module"] = duplicate[0]["module"]
        duplicate[1]["attribute"] = duplicate[0]["attribute"]
        samples.append(duplicate)

        for routers in samples:
            with (
                self.subTest(routers=routers),
                tempfile.TemporaryDirectory() as temp_dir,
            ):
                path = Path(temp_dir) / "manifest.json"
                path.write_text(json.dumps({"version": 1, "routers": routers}))
                with self.assertRaises(ValueError):
                    self.generator.load_manifest(path)

    def test_every_manifest_module_and_attribute_exists_statically(self) -> None:
        for entry in self.routers:
            module_path = (API_ROOT / Path(*entry["module"].split("."))).with_suffix(
                ".py"
            )
            self.assertTrue(module_path.is_file(), entry["module"])
            tree = ast.parse(module_path.read_text(encoding="utf-8-sig"))
            self.assertIn(entry["attribute"], _assigned_names(tree), entry["module"])

    def test_generator_is_deterministic_and_committed_output_is_current(self) -> None:
        first = self.generator.render(self.routers)
        second = self.generator.render(self.generator.load_manifest(MANIFEST_PATH))
        self.assertEqual(first, second)
        self.assertEqual(first, AGGREGATE_PATH.read_text(encoding="utf-8"))
        checked = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, checked.returncode, checked.stderr)

    def test_main_registers_domains_in_manifest_order(self) -> None:
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        create_app = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "create_app"
        )
        factories = []
        for node in ast.walk(create_app):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            if node.func.attr != "include_router" or not node.args:
                continue
            child = node.args[0]
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id.startswith("create_")
                and child.func.id.endswith("_router")
            ):
                factories.append(
                    child.func.id.removeprefix("create_").removesuffix("_router")
                )
        self.assertEqual(list(DOMAIN_ORDER), factories)

    def test_migration_runs_outside_best_effort_startup_boundary(self) -> None:
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        lifespan = next(
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan"
        )
        executable = [
            node
            for node in lifespan.body
            if not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
        ]
        assignments = {
            target.id: node.value
            for node in executable
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        migration_call = assignments["migration_mode"]
        self.assertIsInstance(migration_call, ast.Call)
        self.assertIsInstance(migration_call.func, ast.Name)
        self.assertEqual("run_migrations", migration_call.func.id)
        bootstrap_if = next(
            node
            for node in executable
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "legacy_bootstrap"
        )
        bootstrap_calls = {
            node.func.id
            for node in ast.walk(bootstrap_if)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn("init_schema", bootstrap_calls)
        source = MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn('"legacy-bootstrap"', source)


class RouterManifestRuntimeTests(unittest.TestCase):
    def test_runtime_routes_match_pre_manifest_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "router-probe.json"
            env = os.environ.copy()
            env["AOS_ROUTER_API_PACKAGE"] = str(API_ROOT / "aos_api")
            env["AOS_ROUTER_PROBE_OUTPUT"] = str(output)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            probed = subprocess.run(
                [sys.executable, "-c", textwrap.dedent(RUNTIME_PROBE)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if probed.returncode != 0:
                self.fail(
                    "runtime router probe failed; this is not a pass or skip:\n"
                    f"stdout={probed.stdout}\nstderr={probed.stderr}"
                )
            result = json.loads(output.read_text())

        # Runtime inventory includes FastAPI's four framework routes; the
        # exported business-route inventory intentionally filters those out.
        self.assertEqual(4317, result["count"])
        self.assertEqual(
            "66f00cd17cb135c45f83f3e0ac32391724ada83cbd7e602d349c8a39263ab0d2",
            result["sha256"],
        )
        self.assertEqual(2535, result["openapi_paths"])
        self.assertEqual(EXPECTED_DUPLICATES, result["duplicates"])
        self.assertEqual(
            [],
            [item for item in result["duplicates"] if item[0].startswith("/v1/aip/")],
        )
        self.assertEqual([], result["missing_critical"])
        self.assertTrue(result["managed_skipped_bootstrap"])
        self.assertTrue(result["migration_failure_propagated"])


if __name__ == "__main__":
    unittest.main()
