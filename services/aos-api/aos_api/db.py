"""Dev PG access — Wave-2 Meta Store (T2.2+)."""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import (
    TenantScope,
    apply_transaction_scope,
    current_tenant_scope,
)

log = get_logger("aos-api.db")

DEFAULT_DSN = "postgresql://aos_app:aos_dev_only_change_me@127.0.0.1:5433/aos_meta"


def get_dsn() -> str:
    return os.getenv("AOS_DATABASE_URL", DEFAULT_DSN)


@contextmanager
def connect(scope: TenantScope | None = None) -> Iterator[psycopg.Connection]:
    dsn = get_dsn()
    log.debug("db_connect host_port_from_env=%s", "AOS_DATABASE_URL" in os.environ)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        # 强制 UTF-8，避免客户端/驱动默认编码把中文写成 ???
        conn.execute("SET client_encoding TO 'UTF8'")
        effective_scope = scope if scope is not None else current_tenant_scope()
        if effective_scope is not None:
            apply_transaction_scope(conn, effective_scope)
        yield conn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta_object_type (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  published BOOLEAN NOT NULL DEFAULT FALSE,
  properties JSONB NOT NULL DEFAULT '[]'::jsonb,
  required_markings JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS meta_action_type (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  object_type TEXT NOT NULL,
  parameters JSONB NOT NULL DEFAULT '[]'::jsonb,
  required_markings JSONB NOT NULL DEFAULT '[]'::jsonb,
  submission_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS draft_dataset (
  id TEXT PRIMARY KEY,
  action_type_id TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT,
  title TEXT NOT NULL DEFAULT '',
  proposed JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'proposed',
  created_by TEXT NOT NULL,
  org_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT draft_status_chk CHECK (status IN ('proposed','approved','rejected'))
);

CREATE TABLE IF NOT EXISTS obj_instance (
  object_type TEXT NOT NULL REFERENCES meta_object_type(id),
  object_id TEXT NOT NULL,
  props JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (object_type, object_id)
);

CREATE TABLE IF NOT EXISTS graph_edge (
  src_type TEXT NOT NULL,
  src_id TEXT NOT NULL,
  rel TEXT NOT NULL,
  dst_type TEXT NOT NULL,
  dst_id TEXT NOT NULL,
  PRIMARY KEY (src_type, src_id, rel, dst_type, dst_id)
);

CREATE TABLE IF NOT EXISTS wiki_page (
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  body JSONB NOT NULL DEFAULT '{}'::jsonb,
  org_id TEXT NOT NULL DEFAULT 'dev-org',
  project_id TEXT NOT NULL DEFAULT 'dev-project',
  PRIMARY KEY (object_type, object_id)
);

CREATE TABLE IF NOT EXISTS wiki_page_version (
  id BIGSERIAL PRIMARY KEY,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  body JSONB NOT NULL DEFAULT '{}'::jsonb,
  draft_id TEXT,
  org_id TEXT NOT NULL DEFAULT 'dev-org',
  project_id TEXT NOT NULL DEFAULT 'dev-project',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wiki_page_version_obj
  ON wiki_page_version (object_type, object_id, id DESC);

CREATE TABLE IF NOT EXISTS meta_branch (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  base_ref TEXT NOT NULL DEFAULT 'main',
  readonly BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS obj_branch_overlay (
  branch_id TEXT NOT NULL REFERENCES meta_branch(id) ON DELETE CASCADE,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  props JSONB NOT NULL DEFAULT '{}'::jsonb,
  op TEXT NOT NULL DEFAULT 'upsert',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (branch_id, object_type, object_id)
);

CREATE TABLE IF NOT EXISTS meta_link_type (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  src_type TEXT NOT NULL,
  dst_type TEXT NOT NULL,
  rel TEXT NOT NULL,
  cardinality TEXT NOT NULL DEFAULT 'MANY_TO_MANY',
  expected_edges BIGINT NOT NULL DEFAULT 0,
  mdo_approved BOOLEAN NOT NULL DEFAULT FALSE,
  published BOOLEAN NOT NULL DEFAULT FALSE,
  description TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS funnel_status (
  object_type TEXT PRIMARY KEY,
  stage TEXT NOT NULL DEFAULT 'ingest',
  detail JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS authz_tuple (
  user_key TEXT NOT NULL,
  relation TEXT NOT NULL,
  object_key TEXT NOT NULL,
  PRIMARY KEY (user_key, relation, object_key)
);
"""


def init_schema() -> None:
    with connect() as conn:
        conn.execute(SCHEMA_SQL)
        # Existing DBs created before scheme 55
        conn.execute(
            """
            ALTER TABLE meta_object_type
            ADD COLUMN IF NOT EXISTS required_markings JSONB NOT NULL DEFAULT '[]'::jsonb
            """
        )
        conn.execute(
            """
            ALTER TABLE meta_action_type
            ADD COLUMN IF NOT EXISTS submission_criteria JSONB NOT NULL DEFAULT '[]'::jsonb
            """
        )
        from aos_api.apollo_catalog import ensure_schema as ensure_apollo_schema
        from aos_api.branch_store import ensure_overlay_table

        ensure_apollo_schema(conn)
        ensure_overlay_table(conn)
        from aos_api.twa_pg import ensure_schema as ensure_twa_schema

        ensure_twa_schema(conn)
        from aos_api.retention_jobs import ensure_lifecycle_schema

        ensure_lifecycle_schema(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wiki_page_version (
              id BIGSERIAL PRIMARY KEY,
              object_type TEXT NOT NULL,
              object_id TEXT NOT NULL,
              body JSONB NOT NULL DEFAULT '{}'::jsonb,
              draft_id TEXT,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wiki_page_version_obj
              ON wiki_page_version (object_type, object_id, id DESC)
            """
        )
        # TWA.8 — wiki tenant columns
        conn.execute(
            """
            ALTER TABLE wiki_page
            ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT 'dev-org'
            """
        )
        conn.execute(
            """
            ALTER TABLE wiki_page
            ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'dev-project'
            """
        )
        conn.execute(
            """
            ALTER TABLE wiki_page_version
            ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT 'dev-org'
            """
        )
        conn.execute(
            """
            ALTER TABLE wiki_page_version
            ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'dev-project'
            """
        )
        conn.commit()
    log.info("db_schema_ready")
    try:
        from aos_api.twa_pg import bootstrap as twa_bootstrap

        twa_bootstrap()
    except Exception as exc:  # noqa: BLE001  # pragma: no cover
        log.warning("twa_store_bootstrap_skip err=%s", exc)


def repair_demo_workorders(conn=None) -> None:
    """Keep demo WorkOrders stable for Inbox filters / conflict tests."""
    from aos_api.demo.scope import TEST_SCOPE

    samples = [
        (
            "WorkOrder",
            "wo-1001",
            '{"title":"机房巡检-A区","status":"open","site":"DC-East","priority":"P1","internalCost":1280}',
        ),
        (
            "WorkOrder",
            "wo-1002",
            '{"title":"链路告警复核","status":"in_progress","site":"DC-West","priority":"P0","internalCost":640}',
        ),
        (
            "WorkOrder",
            "wo-1003",
            '{"title":"备件更换","status":"open","site":"DC-East","priority":"P2","internalCost":320}',
        ),
        # 36 §7 · MySQL 供数样例（防 utf8 双重编码乱码残留）
        (
            "WorkOrder",
            "mysql-wo-001",
            '{"title":"MySQL供数-巡检单","status":"open","site":"DC-East","priority":"P1"}',
        ),
        (
            "WorkOrder",
            "mysql-wo-002",
            '{"title":"MySQL供数-备件","status":"in_progress","site":"DC-West","priority":"P0"}',
        ),
    ]

    def _run(c) -> None:
        for t, i, p in samples:
            c.execute(
                """
                INSERT INTO obj_instance
                  (object_type, object_id, props, org_id, project_id)
                VALUES (%s,%s,%s::jsonb,%s,%s)
                ON CONFLICT (org_id, project_id, object_type, object_id)
                DO UPDATE SET props = EXCLUDED.props
                WHERE obj_instance.org_id=EXCLUDED.org_id
                  AND obj_instance.project_id=EXCLUDED.project_id
                """,
                (t, i, p, *TEST_SCOPE.key),
            )

    if conn is None:
        with connect() as c:
            _run(c)
            c.commit()
    else:
        _run(conn)


_WORKORDER_PROPS = (
    "["
    '{"name":"title","type":"string"},'
    '{"name":"status","type":"string"},'
    '{"name":"site","type":"string"},'
    '{"name":"priority","type":"string"},'
    '{"name":"internalCost","type":"number","requiredMarkings":["secret"]}'
    "]"
)


def ensure_field_marking_seed(conn=None) -> None:
    """TX.4 field-level: WorkOrder.internalCost requires secret marking."""
    def _run(c) -> None:
        c.execute(
            """
            INSERT INTO meta_object_type (id, name, description, published, properties)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET properties = EXCLUDED.properties
            """,
            (
                "WorkOrder",
                "工单",
                "Wave-2 seed Object Type",
                True,
                _WORKORDER_PROPS,
            ),
        )
        log.info("field_marking_seed_ensured objectType=WorkOrder field=internalCost")

    if conn is None:
        with connect() as c:
            _run(c)
            c.commit()
    else:
        _run(conn)


def ensure_inherit_openfga_seed(conn=None) -> None:
    """TX.4 scheme 55: Site ObjectType schema only (no demo instances).

    测试数据（site-east / wo-fga-demo / authz_tuple）已迁移到
    ``aos_api.demo.workorder_seed``，这里只保留 schema 级 ObjectType。
    """
    def _run(c) -> None:
        c.execute(
            """
            INSERT INTO meta_object_type (id, name, description, published, properties, required_markings)
            VALUES (%s, %s, %s, %s, '[]'::jsonb, '[]'::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            ("Site", "站点", "Marking inheritance parent (scheme 55)", True),
        )
        log.info("inherit_openfga_seed_ensured objectType=Site schema_only")

    if conn is None:
        with connect() as c:
            _run(c)
            c.commit()
    else:
        _run(conn)


def ensure_system_meta() -> None:
    """系统启动时调用的元数据初始化（不含任何测试数据）。

    包含：
      - field marking seed（WorkOrder ObjectType schema 定义）
      - inherit_openfga seed（Site ObjectType schema 定义）
      - apollo catalog seed
      - lt-related-to 默认 link type

    **不**包含：dev-org / dev-project / 工单样例 / 订单 / 模块等测试数据。
    测试数据请用 ``aos_api.demo.seed_test_org()``。
    """
    with connect() as conn:
        ensure_field_marking_seed(conn)
        ensure_inherit_openfga_seed(conn)
        from aos_api.apollo_catalog import ensure_seed as ensure_apollo_catalog_seed

        ensure_apollo_catalog_seed(conn)
        conn.execute(
            """
            INSERT INTO meta_link_type (
              id, name, src_type, dst_type, rel, cardinality,
              expected_edges, mdo_approved, published, description
            )
            VALUES (
              'lt-related-to', '工单关联', 'WorkOrder', 'WorkOrder', 'related_to',
              'MANY_TO_MANY', 1, FALSE, TRUE, 'Wave-2 seed Link Type'
            )
            ON CONFLICT DO NOTHING
            """
        )
        conn.commit()
        log.debug("ensure_system_meta_done branches_and_link_types_ensured")


def seed_if_empty() -> None:
    """[Deprecated] 兼容入口：系统元数据 + 测试组织数据。

    保留是为了向后兼容现有测试代码（conftest 等）。生产启动请用
    ``ensure_system_meta``，开发/测试请显式调 ``aos_api.demo.seed_test_org``。

    内部行为：``ensure_system_meta() + demo.seed_test_org()``
    """
    ensure_system_meta()
    try:
        from aos_api.demo import seed_test_org

        seed_test_org()
    except Exception as exc:  # noqa: BLE001
        log.warning("seed_test_org_skipped: %s", exc)
