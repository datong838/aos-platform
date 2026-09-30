"""Isolated PostgreSQL proof that ordinary runtime cannot forge network approval."""

import os
import subprocess
import uuid

import pytest


_CONTAINER = os.environ.get("AOS_BG00CJ_TEST_CONTAINER", "")
_ALLOWED_CONTAINERS = {"aos-bg00ce-isolated-pg", "aos-bg00ck-isolated-pg"}
_DB = "aos_current_preview_20260927"


def _require_isolated_container() -> None:
    if _CONTAINER not in _ALLOWED_CONTAINERS:
        pytest.skip("explicit BG00cj/BG00ck isolated container required")


def _probe(sql: str, *, user: str = "postgres") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "--context", "colima-aos-a0v-test-only", "exec", "-i", _CONTAINER,
         "psql", "-X", "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose",
         "-U", user, "-d", _DB, "-At"],
        input=sql, capture_output=True, text=True, timeout=30, check=False,
    )


def _seed(proposal: str) -> str:
    return f"""BEGIN;
      INSERT INTO aip_action_proposal
        (org_id,project_id,proposal_id,action_type_id,action_type_revision_hash,
         action_type_snapshot,purpose,risk_level,policy_snapshot,payload,proposal_hash,
         action_binding_hash,approval_policy_hash,status,expires_at,idempotency_key,
         request_hash,version,created_by)
      VALUES ('org-org','dev-project','{proposal}','aip_activate_network_policy',
        '{'a' * 64}','{{}}'::jsonb,'isolated DB gate proof','R2','{{}}'::jsonb,
        '{{}}'::jsonb,'{'b' * 64}','{'e' * 64}','{'f' * 64}',
        'drafted',now()+interval '1 hour','{proposal}','{'c' * 64}',1,
        'bg00cj-maker-testonly');
    """


@pytest.mark.parametrize("mutation", ["event_insert", "proposal_hash_update"])
def test_runtime_cannot_forge_network_approval(mutation: str) -> None:
    _require_isolated_container()
    proposal = f"bg00cj-{uuid.uuid4().hex}"
    event = f"bg00cj-event-{uuid.uuid4().hex}"
    seed = _seed(proposal) + """SET LOCAL ROLE aos_runtime;
      SET LOCAL aos.org_id='org-org';
      SET LOCAL aos.project_id='dev-project';
      SELECT session_user,current_user,current_setting('aos.org_id'),
             current_setting('aos.project_id');
    """
    if mutation == "event_insert":
        attack = f"""INSERT INTO aip_action_approval_event
          (org_id,project_id,approval_event_id,proposal_id,proposal_version,
           proposal_hash,decision,actor_id,idempotency_key,request_hash)
          VALUES ('org-org','dev-project','{event}','{proposal}',1,
                  '{'b' * 64}','approved','bg00cj-checker-testonly',
                  '{event}','{'d' * 64}');"""
    else:
        attack = f"""UPDATE aip_action_proposal SET proposal_hash='{'0' * 64}'
          WHERE org_id='org-org' AND project_id='dev-project'
            AND proposal_id='{proposal}';"""
    result = _probe(seed + attack + "\nROLLBACK;\n")
    assert result.returncode != 0, result.stdout
    expected = ("NETWORK_APPROVAL_ISSUER_REQUIRED" if mutation == "event_insert"
                else "NETWORK_PROPOSAL_CORE_IMMUTABLE")
    assert expected in result.stderr, result.stderr
    assert "42501" in result.stderr


def test_issuer_can_issue_event_but_not_maker_proposal() -> None:
    _require_isolated_container()
    proposal = f"bg00cj-{uuid.uuid4().hex}"
    seed = _seed(proposal)
    positive = _probe(seed + f"""
      SET SESSION AUTHORIZATION aos_network_approval_issuer;
      SET LOCAL ROLE aos_runtime;
      SET LOCAL aos.org_id='org-org';
      SET LOCAL aos.project_id='dev-project';
      SELECT session_user,current_user;
      INSERT INTO aip_action_approval_event
        (org_id,project_id,approval_event_id,proposal_id,proposal_version,
         proposal_hash,decision,actor_id,idempotency_key,request_hash)
      VALUES ('org-org','dev-project','{proposal}-event','{proposal}',1,
        '{'b' * 64}','approved','bg00cj-checker-testonly',
        '{proposal}-event','{'d' * 64}');
      UPDATE aip_action_proposal SET status='approved',version=2,updated_at=now()
        WHERE org_id='org-org' AND project_id='dev-project' AND proposal_id='{proposal}';
      ROLLBACK;
    """)
    assert positive.returncode == 0, positive.stderr
    assert "aos_network_approval_issuer|aos_runtime" in positive.stdout
    assert "INSERT 0 1" in positive.stdout and "UPDATE 1" in positive.stdout
    denied = _probe(seed.replace("BEGIN;", "BEGIN;\n"
                                  "SET SESSION AUTHORIZATION aos_network_approval_issuer;\n"
                                  "SET LOCAL ROLE aos_runtime;\n"
                                  "SET LOCAL aos.org_id='org-org';\n"
                                  "SET LOCAL aos.project_id='dev-project';", 1)
                    + "ROLLBACK;\n")
    assert denied.returncode != 0
    assert "NETWORK_PROPOSAL_MAKER_ROLE_REQUIRED" in denied.stderr
    assert "42501" in denied.stderr
    login = _probe("SELECT session_user;", user="aos_network_approval_issuer")
    assert login.returncode != 0
    assert "not permitted to log in" in login.stderr


@pytest.mark.parametrize("mutation", ["UPDATE", "DELETE"])
def test_network_approval_event_is_append_only(mutation: str) -> None:
    _require_isolated_container()
    proposal = f"bg00cj-{uuid.uuid4().hex}"
    event = f"{proposal}-event"
    attack = (f"UPDATE aip_action_approval_event SET reason='forged' WHERE "
              f"org_id='org-org' AND project_id='dev-project' AND approval_event_id='{event}';"
              if mutation == "UPDATE" else
              f"DELETE FROM aip_action_approval_event WHERE org_id='org-org' "
              f"AND project_id='dev-project' AND approval_event_id='{event}';")
    result = _probe(_seed(proposal) + f"""
      SET SESSION AUTHORIZATION aos_network_approval_issuer;
      SET LOCAL ROLE aos_runtime;
      SET LOCAL aos.org_id='org-org';
      SET LOCAL aos.project_id='dev-project';
      INSERT INTO aip_action_approval_event
        (org_id,project_id,approval_event_id,proposal_id,proposal_version,
         proposal_hash,decision,actor_id,idempotency_key,request_hash)
      VALUES ('org-org','dev-project','{event}','{proposal}',1,
        '{'b' * 64}','approved','bg00cj-checker-testonly',
        '{event}','{'d' * 64}');
      SET SESSION AUTHORIZATION DEFAULT;
      SET LOCAL ROLE aos_runtime;
      {attack}
      ROLLBACK;
    """)
    assert result.returncode != 0, result.stdout
    assert "NETWORK_APPROVAL_EVENT_IMMUTABLE" in result.stderr, result.stderr
    assert "42501" in result.stderr


def test_generic_action_table_path_remains_available() -> None:
    _require_isolated_container()
    proposal = f"bg00cj-generic-{uuid.uuid4().hex}"
    result = _probe(f"""BEGIN;
      INSERT INTO aip_action_proposal
        (org_id,project_id,proposal_id,action_type_id,action_type_revision_hash,
         action_type_snapshot,purpose,risk_level,policy_snapshot,payload,proposal_hash,
         status,expires_at,idempotency_key,request_hash,version,created_by)
      VALUES ('org-org','dev-project','{proposal}','bg00cj_generic_testonly',
        '{'a' * 64}','{{}}'::jsonb,'generic table guard regression','R0',
        '{{}}'::jsonb,'{{}}'::jsonb,'{'b' * 64}','drafted',
        now()+interval '1 hour','{proposal}','{'c' * 64}',1,
        'bg00cj-generic-maker-testonly');
      SET LOCAL ROLE aos_runtime;
      SET LOCAL aos.org_id='org-org';
      SET LOCAL aos.project_id='dev-project';
      INSERT INTO aip_action_approval_event
        (org_id,project_id,approval_event_id,proposal_id,proposal_version,
         proposal_hash,decision,actor_id,idempotency_key,request_hash)
      VALUES ('org-org','dev-project','{proposal}-event','{proposal}',1,
        '{'b' * 64}','approved','bg00cj-generic-checker-testonly',
        '{proposal}-event','{'d' * 64}');
      ROLLBACK;
    """)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("INSERT 0 1") == 2
