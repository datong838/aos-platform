"""Minimal isolated-PG projection of AIP-1/AIP-4 content Owner tables.

The budget fixture owns a random schema; it must not copy production/public
tables or silently depend on a separately bootstrapped shared database.
"""


def install_lineage(owner):
    owner.execute('''CREATE TABLE aip_lineage_event (
        org_id text NOT NULL,project_id text NOT NULL,event_id text NOT NULL,
        lineage_id text NOT NULL,root_type text NOT NULL,root_id text NOT NULL,
        sequence bigint NOT NULL,event_type text NOT NULL,subject_ref jsonb,
        artifact_ref jsonb,payload_hash text NOT NULL,quality text NOT NULL,
        occurred_at timestamptz NOT NULL,observed_at timestamptz NOT NULL,
        source_kind text,source_id text,source_hash text,
        PRIMARY KEY(org_id,project_id,event_id),
        UNIQUE(org_id,project_id,lineage_id,sequence),
        CONSTRAINT aip_lineage_event_root_type_check CHECK(root_type IN
            ('task_run','action','eval_run','publication','research_job','legacy_decision_lineage')),
        CONSTRAINT aip_lineage_event_source_kind_check CHECK(source_kind IS NULL OR source_kind IN
            ('task_run','step_run','checkpoint','artifact','evidence','action_event',
             'action_receipt','eval_run','eval_run_event','eval_report','publication_event')),
        CHECK(event_type IN ('input','retrieval','model','tool','action','artifact','eval',
            'approval','receipt','effect_review','memory_candidate','fallback','reconcile','error')),
        CHECK(quality IN ('measured','estimated','unknown')),
        CHECK(sequence>=1),CHECK(length(payload_hash)=64),
        CHECK(observed_at>=occurred_at),
        CHECK((source_kind IS NULL AND source_id IS NULL AND source_hash IS NULL)
           OR (source_kind IS NOT NULL AND source_id IS NOT NULL AND length(source_hash)=64))
    )''')
    _scope(owner,'aip_lineage_event')


def install_artifact(owner):
    owner.execute('''CREATE TABLE aip_artifact (
        org_id text NOT NULL,project_id text NOT NULL,artifact_id text NOT NULL,
        run_id text,artifact_type text NOT NULL,content_ref text,schema_ref text,
        source jsonb NOT NULL DEFAULT '{}'::jsonb,
        evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
        marking jsonb NOT NULL DEFAULT '[]'::jsonb,
        content_hash text NOT NULL,metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
        created_by text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
        family_id text,family_revision bigint,family_role text,profile text,platform text,
        rendition_spec jsonb,rendition_spec_hash char(64),lineage_refs jsonb,
        PRIMARY KEY(org_id,project_id,artifact_id),
        CHECK(content_hash ~ '^[0-9a-f]{64}$')
    )''')
    _scope(owner,'aip_artifact')


def _scope(owner,table):
    owner.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
    owner.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
    owner.execute(f'''CREATE POLICY tenant_scope_{table} ON {table} TO aos_runtime
        USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))''')
