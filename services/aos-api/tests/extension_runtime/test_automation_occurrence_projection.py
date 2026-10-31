"""Offline SQL-definition evidence only; native projection and locks need PG."""
from pathlib import Path
import re
import pytest
from pglast import parse_sql, parser

SQL_FILE=Path(__file__).resolve().parents[2]/'aos_api/automation_occurrence_projection_authority.sql'
S=('org_id','project_id','policy_id','policy_revision','policy_hash','operation_id','installation_id','generation','execution_epoch','timezone','cadence','weekly_day','local_time','effective_from','effective_until','approved')
O=('org_id','project_id','occurrence_id','policy_id','policy_revision','policy_hash','operation_id','installation_id','generation','execution_epoch','scheduled_at','local_slot','trigger_source','source_event_id','deadline','created_at')
A=('org_id','project_id','attempt_id','occurrence_id','claim_owner','target_idempotency_key','claimed_at','claim_until')
CASES=(('automation_schedule_binding',S,('enabled','watermark','revision')),
       ('automation_occurrence',O,('status','claim_owner','claim_until','receipt_ref','updated_at')),
       ('automation_occurrence_dispatch_attempt',A,('status','receipt_ref','resolved_at')))


@pytest.fixture
def definitions():
    assert SQL_FILE.is_file(), 'S/O/A projection SQL asset is missing'
    text=SQL_FILE.read_text()
    matches=re.findall(r'CREATE FUNCTION public\.(\w+)\(\)\s*RETURNS trigger\s*LANGUAGE plpgsql\s*SECURITY DEFINER\s*SET search_path = pg_catalog, pg_temp\s*AS \$projection\$(.*?)\$projection\$;',text,re.S)
    assert len(matches)==3
    return text,dict(matches)


@pytest.mark.parametrize('table,identity,mutable',CASES)
def test_same_version_identity_is_exact_null_safe_and_mutable_columns_are_not_frozen(definitions,table,identity,mutable):
    _,functions=definitions;body=functions[table+'_projection_guard_v1']
    update=body.split("IF TG_OP = 'UPDATE'",1)[1].split("ELSIF TG_OP = 'INSERT'",1)[0]
    rows=re.findall(r'ROW\(([^()]+)\)',update,re.S)
    assert len(rows)==2 and ') IS DISTINCT FROM ROW(' in ' '.join(update.split())
    for prefix,row in zip(('OLD','NEW'),rows):assert [v.strip() for v in row.split(',')]==[prefix+'.'+v for v in identity]
    for field in mutable:assert not re.search(r'\b(?:OLD|NEW)\.'+field+r'\b',update)
    assert 'SELECT ' not in update and 'RETURN NEW;' in update


@pytest.mark.parametrize('table,identity,mutable',CASES)
def test_context_and_history_mutations_never_bypass_projection(definitions,table,identity,mutable):
    text,functions=definitions;body=functions[table+'_projection_guard_v1'];flat=' '.join(body.split())
    for fragment in ("TG_TABLE_SCHEMA <> 'public'", "TG_TABLE_NAME <> '"+table+"'", "TG_WHEN <> 'BEFORE'", 'TG_NARGS <> 0'):
        assert fragment in flat
    assert "TG_OP = 'DELETE' AND TG_LEVEL = 'ROW'" in flat
    assert "TG_OP = 'TRUNCATE' AND TG_LEVEL = 'STATEMENT'" in flat
    assert 'RETURN OLD' not in body and 'RETURN NULL' not in body
    assert "ERRCODE = '23514'" in body and "ERRCODE = '55000'" in body
    assert not re.search(r'\b(?:EXECUTE|COMMIT|ROLLBACK|GRANT|set_config)\b',body,re.I)


def test_schedule_insert_holds_dispatch_then_runtime_share_locks_on_exact_nonkey_projection(definitions):
    _,functions=definitions;body=functions['automation_schedule_binding_projection_guard_v1']
    assert body.index('FROM public.extension_operation_dispatch_binding')<body.index('FROM public.extension_runtime_binding')
    assert body.count('FOR SHARE NOWAIT')==2 and 'KEY SHARE' not in body
    assert 'd.operation_id = NEW.operation_id' in body
    assert 'b.installation_id = NEW.installation_id AND b.generation = NEW.generation' in body
    assert 'ROW(dispatch.installation_id, dispatch.generation, dispatch.execution_epoch)' in body
    assert 'ROW(NEW.installation_id, NEW.generation, NEW.execution_epoch)' in body
    assert 'binding.execution_epoch IS DISTINCT FROM NEW.execution_epoch' in body
    assert not any(word in body for word in ('.enabled','.operation_fence','.observed_state','.desired_state'))


def test_occurrence_insert_reads_one_exact_policy_parent_and_preserves_historical_statuses(definitions):
    _,functions=definitions;body=functions['automation_occurrence_projection_guard_v1']
    assert 'FROM public.automation_schedule_binding' in body and body.count('FOR SHARE NOWAIT')==1
    assert 's.policy_id = NEW.policy_id AND s.policy_revision = NEW.policy_revision' in body
    assert 'ROW(schedule.policy_hash, schedule.operation_id, schedule.installation_id, schedule.generation, schedule.execution_epoch)' in body
    assert not any(word in body for word in ('.enabled','.approved','NEW.status'))


def test_attempt_insert_has_real_claim_parent_original_target_key_and_distinct_lease_semantics(definitions):
    _,functions=definitions;body=functions['automation_occurrence_dispatch_attempt_projection_guard_v1']
    assert 'FROM public.automation_occurrence' in body and body.count('FOR SHARE NOWAIT')==1
    assert "occurrence.status IS DISTINCT FROM 'claimed'" in body
    assert 'occurrence.claim_owner IS DISTINCT FROM NEW.claim_owner' in body
    assert 'occurrence.claim_until IS DISTINCT FROM NEW.claim_until' in body
    assert "NEW.target_idempotency_key IS DISTINCT FROM 'automation-occurrence:' || NEW.occurrence_id::text" in body
    assert 'NEW.claimed_at >= NEW.claim_until' in body and 'NEW.claimed_at >= occurrence.deadline' in body
    assert 'NEW.claim_until > occurrence.deadline' not in body and 'clock_timestamp' not in body
    assert 'NEW.status' not in body


def test_exact_installation_cannot_create_roles_or_silently_override_existing_protection(definitions):
    text,functions=definitions
    assert len(parse_sql(text))==15
    for table,_,_ in CASES:
        function='public.'+table+'_projection_guard_v1'
        assert f'REVOKE ALL ON FUNCTION {function}() FROM PUBLIC;' in text
        assert f'ALTER FUNCTION {function}() OWNER TO aos_terminal_source_projection_owner;' in text
        assert f'BEFORE INSERT OR UPDATE OR DELETE ON public.{table}' in text
        assert f'BEFORE TRUNCATE ON public.{table}' in text
    for bad in ('CREATE ROLE','GRANT ','OR REPLACE','IF NOT EXISTS','DISABLE TRIGGER','SECURITY INVOKER','ALTER TABLE','DROP '):assert bad not in text
    assert len(functions)==3


def test_sql_and_all_plpgsql_definitions_parse_without_executing_database_calls(definitions):
    text,_=definitions
    assert parse_sql(text)
    # v8.4's JSON wrapper emits malformed trees even for a minimal trigger.
    # The underlying compiler still rejects malformed PL/pgSQL with ParseError.
    compiled=parser.parse_plpgsql_json(text)
    assert compiled.count('PLpgSQL_function')==3


def test_underlying_plpgsql_compiler_rejects_corrupted_trigger_body(definitions):
    text,_=definitions
    malformed=text.replace('RETURN NEW;','RETURN (;',1)
    assert malformed!=text
    with pytest.raises(parser.ParseError):parser.parse_plpgsql_json(malformed)
