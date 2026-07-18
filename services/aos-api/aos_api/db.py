"""Dev PG access — Wave-2 Meta Store (T2.2+)."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.db")

DEFAULT_DSN = "postgresql://aos_app:aos_dev_only_change_me@127.0.0.1:5433/aos_meta"


def get_dsn() -> str:
    return os.getenv("AOS_DATABASE_URL", DEFAULT_DSN)


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    dsn = get_dsn()
    log.debug("db_connect host_port_from_env=%s", "AOS_DATABASE_URL" in os.environ)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
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
  PRIMARY KEY (object_type, object_id)
);

CREATE TABLE IF NOT EXISTS meta_branch (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  base_ref TEXT NOT NULL DEFAULT 'main',
  readonly BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
        from aos_api.apollo_catalog import ensure_schema as ensure_apollo_schema

        ensure_apollo_schema(conn)
        conn.commit()
    log.info("db_schema_ready")


def repair_demo_workorders(conn=None) -> None:
    """Keep demo WorkOrders stable for Inbox filters / conflict tests."""
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
                INSERT INTO obj_instance (object_type, object_id, props)
                VALUES (%s,%s,%s::jsonb)
                ON CONFLICT (object_type, object_id)
                DO UPDATE SET props = EXCLUDED.props
                """,
                (t, i, p),
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
    """TX.4 scheme 55: marking inheritance + OpenFGA demo tuples."""
    def _run(c) -> None:
        c.execute(
            """
            INSERT INTO meta_object_type (id, name, description, published, properties, required_markings)
            VALUES (%s, %s, %s, %s, '[]'::jsonb, '[]'::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            ("Site", "站点", "Marking inheritance parent (scheme 55)", True),
        )
        c.execute(
            """
            INSERT INTO obj_instance (object_type, object_id, props)
            VALUES (
              'Site', 'site-east',
              '{"name":"DC-East","_requiredMarkings":["restricted"]}'::jsonb
            )
            ON CONFLICT (object_type, object_id)
            DO UPDATE SET props = EXCLUDED.props
            """
        )
        c.execute(
            """
            INSERT INTO graph_edge (src_type, src_id, rel, dst_type, dst_id)
            VALUES ('WorkOrder','wo-1003','inherits_markings_from','Site','site-east')
            ON CONFLICT DO NOTHING
            """
        )
        c.execute(
            """
            INSERT INTO obj_instance (object_type, object_id, props)
            VALUES (
              'WorkOrder', 'wo-fga-demo',
              '{"title":"OpenFGA demo","status":"open","site":"DC-East","priority":"P2"}'::jsonb
            )
            ON CONFLICT (object_type, object_id) DO NOTHING
            """
        )
        c.execute(
            """
            INSERT INTO authz_tuple (user_key, relation, object_key)
            VALUES
              ('user:secret-user', 'viewer', 'object:WorkOrder:wo-fga-demo'),
              ('user:secret-user', 'member', 'organization:dev-org'),
              ('organization:dev-org', 'parent', 'project:dev-project'),
              ('user:secret-user', 'bearer', 'marking:restricted'),
              ('user:bearer-only', 'bearer', 'marking:restricted'),
              ('user:field-bearer', 'bearer', 'marking:secret')
            ON CONFLICT DO NOTHING
            """
        )
        log.info(
            "inherit_openfga_seed_ensured wo-1003←site-east · wo-fga-demo · org/project/marking · bearer-only · field-bearer"
        )

    if conn is None:
        with connect() as c:
            _run(c)
            c.commit()
    else:
        _run(conn)


def seed_if_empty() -> None:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM meta_object_type").fetchone()
        if not row or int(row["c"]) == 0:
            conn.execute(
                """
                INSERT INTO meta_object_type (id, name, description, published, properties)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (
                    "WorkOrder",
                    "工单",
                    "Wave-2 seed Object Type",
                    True,
                    _WORKORDER_PROPS,
                ),
            )
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
            ]
            for t, i, p in samples:
                conn.execute(
                    "INSERT INTO obj_instance (object_type, object_id, props) VALUES (%s,%s,%s::jsonb)",
                    (t, i, p),
                )
            conn.execute(
                """
                INSERT INTO graph_edge (src_type, src_id, rel, dst_type, dst_id)
                VALUES ('WorkOrder','wo-1001','related_to','WorkOrder','wo-1003')
                ON CONFLICT DO NOTHING
                """
            )
            conn.execute(
                """
                INSERT INTO wiki_page (object_type, object_id, body)
                VALUES ('WorkOrder','wo-1001','{"summary":"A区巡检知识","fields":{"sla":"4h"}}'::jsonb)
                ON CONFLICT DO NOTHING
                """
            )
            conn.execute(
                """
                INSERT INTO funnel_status (object_type, stage, detail)
                VALUES ('WorkOrder','enrich','{"stages":["ingest","normalize","enrich","publish"]}'::jsonb)
                ON CONFLICT (object_type) DO NOTHING
                """
            )
            log.info("db_seed_workorder_done")
        ensure_field_marking_seed(conn)
        repair_demo_workorders(conn)
        ensure_inherit_openfga_seed(conn)
        from aos_api.apollo_catalog import ensure_seed as ensure_apollo_catalog_seed

        ensure_apollo_catalog_seed(conn)
        # Always ensure branch seed (table may be added after first seed)
        conn.execute(
            """
            INSERT INTO meta_branch (id, name, base_ref, readonly)
            VALUES
              ('main', 'main', 'main', TRUE),
              ('sandbox', 'sandbox', 'main', TRUE)
            ON CONFLICT DO NOTHING
            """
        )
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
        log.debug("db_seed_branches_and_link_types_ensured")
