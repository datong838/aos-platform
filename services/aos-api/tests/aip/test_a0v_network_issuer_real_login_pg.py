"""Real TCP issuer proof on the explicitly provisioned isolated BG00cm clone."""

import os
from pathlib import Path

import pytest
from psycopg import Error, OperationalError, connect


def test_real_scram_issuer_transaction_rolls_back() -> None:
    if os.environ.get("AOS_BG00CM_TEST_CONTAINER") != "aos-bg00ck-isolated-pg":
        pytest.skip("explicit BG00cm isolated container required")
    private_dir = Path(os.environ["AOS_BG00CM_PROOF_DIR"])
    assert private_dir.stat().st_mode & 0o777 == 0o700
    pgpass = private_dir / "issuer.pgpass"
    assert pgpass.stat().st_mode & 0o777 == 0o600
    proposal = (private_dir / "proposal-id").read_text().strip()
    params = dict(host="127.0.0.1", port=18437,
                  dbname="aos_current_preview_20260927",
                  user="aos_network_approval_issuer", connect_timeout=5)
    with pytest.raises(OperationalError):
        connect(**params, password="bg00cm-incorrect-password")
    with connect(**params, passfile=str(pgpass)) as conn:
        before = conn.execute("SELECT session_user,current_user").fetchone()
        assert before == ("aos_network_approval_issuer",) * 2
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute("SET LOCAL aos.org_id='org-org'")
        conn.execute("SET LOCAL aos.project_id='dev-project'")
        assert conn.execute("SELECT session_user,current_user").fetchone() == (
            "aos_network_approval_issuer", "aos_runtime")
        conn.execute("""INSERT INTO aip_action_approval_event
          (org_id,project_id,approval_event_id,proposal_id,proposal_version,
           proposal_hash,decision,actor_id,idempotency_key,request_hash)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
          ("org-org", "dev-project", proposal + "-event", proposal, 1,
           "b" * 64, "approved", "bg00cm-checker-testonly",
           proposal + "-event", "d" * 64))
        conn.execute("""UPDATE aip_action_proposal
          SET status='approved',version=2,updated_at=now()
          WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
          ("org-org", "dev-project", proposal))
        assert conn.execute("""SELECT status,version FROM aip_action_proposal
          WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
          ("org-org", "dev-project", proposal)).fetchone() == ("approved", 2)
        conn.rollback()
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute("SET LOCAL aos.org_id='org-org'")
        conn.execute("SET LOCAL aos.project_id='dev-project'")
        assert conn.execute("""SELECT status,version FROM aip_action_proposal
          WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
          ("org-org", "dev-project", proposal)).fetchone() == ("drafted", 1)
        assert conn.execute("""SELECT count(*) FROM aip_action_approval_event
          WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
          ("org-org", "dev-project", proposal)).fetchone()[0] == 0
        conn.rollback()
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute("SET LOCAL aos.org_id='org-org'")
        conn.execute("SET LOCAL aos.project_id='dev-project'")
        with pytest.raises(Error, match="NETWORK_PROPOSAL_MAKER_ROLE_REQUIRED"):
            conn.execute("""INSERT INTO aip_action_proposal
              (org_id,project_id,proposal_id,action_type_id,action_type_revision_hash,
               action_type_snapshot,purpose,risk_level,policy_snapshot,payload,
               proposal_hash,action_binding_hash,approval_policy_hash,status,
               expires_at,idempotency_key,request_hash,version,created_by)
              VALUES ('org-org','dev-project',%s,'aip_activate_network_policy',
                %s,'{}'::jsonb,'issuer cannot be maker','R2','{}'::jsonb,
                '{}'::jsonb,%s,%s,%s,'drafted',now()+interval '1 hour',
                %s,%s,1,'bg00cm-issuer-testonly')""",
                (proposal + "-issuer-maker", "a" * 64, "b" * 64, "e" * 64,
                 "f" * 64, proposal + "-issuer-maker", "c" * 64))
        conn.rollback()
