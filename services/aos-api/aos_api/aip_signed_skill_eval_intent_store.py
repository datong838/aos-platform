"""Caller-transaction dispatch fencing, never an execution authority or retry loop."""
from uuid import uuid4

from aos_api.tenant_scope import TenantScope


class SkillEvalIntentConflict(RuntimeError):
    pass


def _context(conn, scope: TenantScope, *, write=False):
    if getattr(conn, 'autocommit', None) is not False:
        raise SkillEvalIntentConflict('caller-owned transaction required')
    row = conn.execute("""SELECT current_user AS role,
      current_setting('aos.org_id',true) AS org_id,
      current_setting('aos.project_id',true) AS project_id,
      current_setting('transaction_isolation') AS isolation""").fetchone()
    roles = {'aos_aip_eval_writer'} if write else {'aos_aip_eval_writer', 'aos_runtime'}
    levels = {'serializable'} if write else {'serializable', 'repeatable read'}
    if row['role'] not in roles or row['isolation'] not in levels or (row['org_id'], row['project_id']) != scope.key:
        raise SkillEvalIntentConflict('scoped independent Skill intent transaction required')


class SignedSkillEvalIntentStore:
    """All mutation methods require commit confirmation before any effect.

    Receipt claims still need original signature/Source/Owner/budget admission.
    Serialization failures and commit uncertainty propagate, with no retries.
    """

    def get(self, conn, scope, intent_id):
        _context(conn, scope)
        return conn.execute('SELECT * FROM aip_skill_eval_intent WHERE org_id=%s AND project_id=%s AND intent_id=%s', (*scope.key, intent_id)).fetchone()

    def create(self, conn, scope, *, run_id, idempotency_key, request_hash):
        _context(conn, scope, write=True)
        existing = conn.execute('SELECT * FROM aip_skill_eval_intent WHERE org_id=%s AND project_id=%s AND idempotency_key=%s', (*scope.key, idempotency_key)).fetchone()
        if existing:
            if (existing['run_id'], existing['request_hash']) != (run_id, request_hash):
                raise SkillEvalIntentConflict('Skill intent idempotency contract drifted')
            return existing
        run = conn.execute('SELECT status,version,target_ref FROM aip_eval_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*scope.key, run_id)).fetchone()
        if run is None or run['status'] != 'queued' or run['version'] != 1 or run['target_ref'].get('assetType') != 'skill_template':
            raise SkillEvalIntentConflict('new queued Skill Run required')
        return conn.execute("""INSERT INTO aip_skill_eval_intent
          (org_id,project_id,intent_id,run_id,idempotency_key,request_hash)
          VALUES(%s,%s,%s,%s,%s,%s) RETURNING *""",
          (*scope.key, 'skill-intent-' + uuid4().hex, run_id, idempotency_key, request_hash)).fetchone()

    def claim(self, conn, scope, *, intent_id, expected_version, case_id, purpose, input_hash):
        _context(conn, scope, write=True)
        intent = conn.execute('SELECT * FROM aip_skill_eval_intent WHERE org_id=%s AND project_id=%s AND intent_id=%s FOR UPDATE', (*scope.key, intent_id)).fetchone()
        if intent is None or intent['version'] != expected_version:
            raise SkillEvalIntentConflict('Skill intent version or tenant drifted')
        run = conn.execute('SELECT status FROM aip_eval_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*scope.key, intent['run_id'])).fetchone()
        if run is None or run['status'] != 'running':
            raise SkillEvalIntentConflict('running Skill Run required before dispatch')
        existing = conn.execute('SELECT input_hash FROM aip_skill_eval_dispatch WHERE org_id=%s AND project_id=%s AND intent_id=%s AND case_id=%s AND purpose=%s', (*scope.key, intent_id, case_id, purpose)).fetchone()
        if existing:
            if existing['input_hash'] != input_hash:
                raise SkillEvalIntentConflict('Skill dispatch input drifted')
            return None  # Recorded dispatch is NEVER permission to resend.
        dispatch_id = 'skill-dispatch-' + uuid4().hex
        conn.execute("""INSERT INTO aip_skill_eval_dispatch
          (org_id,project_id,dispatch_id,intent_id,case_id,purpose,input_hash)
          VALUES(%s,%s,%s,%s,%s,%s,%s)""", (*scope.key, dispatch_id, intent_id, case_id, purpose, input_hash))
        row = conn.execute('UPDATE aip_skill_eval_intent SET version=version+1 WHERE org_id=%s AND project_id=%s AND intent_id=%s AND version=%s RETURNING version', (*scope.key, intent_id, expected_version)).fetchone()
        if row is None:
            raise SkillEvalIntentConflict('Skill intent CAS failed')
        return dispatch_id

    def observations(self, conn, scope, dispatch_id):
        _context(conn, scope)
        return conn.execute('SELECT state,result_hash,observed_at FROM aip_skill_eval_dispatch_observation WHERE org_id=%s AND project_id=%s AND dispatch_id=%s ORDER BY observed_at,state', (*scope.key, dispatch_id)).fetchall()

    def observe(self, conn, scope, *, dispatch_id, state, result_hash):
        _context(conn, scope, write=True)
        intent = conn.execute("""SELECT i.intent_id FROM aip_skill_eval_intent i
          JOIN aip_skill_eval_dispatch d USING(org_id,project_id,intent_id)
          WHERE d.org_id=%s AND d.project_id=%s AND d.dispatch_id=%s FOR UPDATE OF i""", (*scope.key, dispatch_id)).fetchone()
        if intent is None:
            raise SkillEvalIntentConflict('Skill dispatch is unavailable')
        rows = self.observations(conn, scope, dispatch_id)
        for row in rows:
            if row['state'] == state:
                if row['result_hash'] != result_hash:
                    raise SkillEvalIntentConflict('Skill result observation drifted')
                return
        if any(row['state'] == 'result_observed' for row in rows):
            raise SkillEvalIntentConflict('Skill result cannot be replaced by unknown')
        conn.execute('INSERT INTO aip_skill_eval_dispatch_observation(org_id,project_id,dispatch_id,state,result_hash) VALUES(%s,%s,%s,%s,%s)', (*scope.key, dispatch_id, state, result_hash))
