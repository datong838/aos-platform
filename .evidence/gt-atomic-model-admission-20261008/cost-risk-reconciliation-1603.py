"""Read-only original fixture cost basis reconciliation; no admission authority."""
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'services/aos-api'))
from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal, DevelopmentRiskProposal
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_model_runtime_contracts import ModelPriceSnapshotRevision

source = repo / '.evidence/gt-judge-call-authority-20261008/whole-manifest-native-green-r5-1602-whole-plan-proof.json'
manifest = json.loads(source.read_text())['manifest']
passfile = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
result = dict(observed_at=datetime.now(timezone.utc).isoformat(), execution_allowed=False,
              source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), sides=[])
with psycopg.connect(host='127.0.0.1', port=5434, user='aos_app',
                    dbname='aos_test_379975a6f96d_ti4_test', passfile=str(passfile),
                    row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
    assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == '7693564235776004128'
    assert conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'] == 'a0v_159'
    for name in ('targetParentBudget', 'judgeParentBudget'):
        parent = manifest[name]; policy_ref = parent['budgetPolicyRef']; price_ref = parent['priceRef']
        policy = conn.execute("SELECT content_hash,payload FROM aip_model_governance_policy_revision WHERE org_id=%s AND project_id=%s AND policy_kind='budget' AND policy_id=%s AND revision=%s", ('org-org', 'dev-project', policy_ref['assetId'], policy_ref['revision'])).fetchone()
        assert policy['content_hash'] == policy_ref['contentHash']
        budget = policy['payload']['budgetRevisionRef']
        receipt = conn.execute("SELECT result_ref FROM aip_budget_receipt WHERE org_id=%s AND project_id=%s AND operation='budget_revision.activate_cost' AND result_ref->>'resourceId'=%s", ('org-org', 'dev-project', budget['assetId'])).fetchall()
        assert len(receipt) == 1
        proposal = conn.execute('SELECT proposal_hash,payload FROM aip_budget_cost_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s', ('org-org', 'dev-project', receipt[0]['result_ref']['proposalId'])).fetchone()
        parsed = BudgetCostBasisProposal.from_canonical_payload(proposal['payload'])
        assert parsed.proposal_hash == proposal['proposal_hash'] and isinstance(parsed.basis, DevelopmentRiskProposal)
        assert parsed.target.budget_id == budget['assetId']
        assert parsed.basis.per_request_risk_minor == parent['upperBoundMinor']
        row = conn.execute('SELECT content_hash,payload FROM aip_model_price_snapshot_revision WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s AND revision=%s', ('org-org', 'dev-project', price_ref['assetId'], price_ref['revision'])).fetchone()
        price = ModelPriceSnapshotRevision.model_validate(row['payload'])
        body = price.model_dump(mode='json', by_alias=True)
        assert row['content_hash'] == price.content_hash == price_ref['contentHash']
        assert canonical_hash({k:v for k,v in body.items() if k not in {'tenant','revision','contentHash','createdBy','createdAt'}}) == price.content_hash
        assert price.development_cost_authorization is not None
        assert all(v is None for v in (price.input_token_price, price.output_token_price, price.cached_token_price))
        def totals():
            values=[]
            for table,column in [('aip_budget_reservation','policy_ref'), ('aip_model_eval_budget_reservation','budget_revision_ref'), ('aip_model_judge_budget_reservation','budget_revision_ref')]:
                values.append(conn.execute(f"SELECT count(*) AS n,coalesce(sum(upper_bound_minor),0) AS risk FROM public.{table} WHERE org_id=%s AND project_id=%s AND {column}->>'resourceId'=%s", ('org-org','dev-project',budget['assetId'])).fetchone())
            return [{k:int(v) for k,v in row.items()} for row in values]
        before=totals(); after=totals(); assert before == after
        result['sides'].append(dict(purpose=name, budget_ref=budget, price_ref=price_ref,
            proposal_hash=parsed.proposal_hash, risk_basis=parsed.basis.model_dump(mode='json',by_alias=True),
            numeric_prices_absent=True, actual_cost_minor=None, ledger_totals=before,
            exact_proposal_and_price_hashes_verified=True))
    result['read_only']=True
    result['limitations']=['Historical fixture windows do not grant current authority', 'Risk request count is reservation-row count, not demonstrated Provider-call count', 'Per-leg 1 minor in manifest is synthetic; neither a known quote nor a held allocation', 'Real transport, Usage, allocation and trusted finalizer remain pending']
with psycopg.connect(host='127.0.0.1', port=5434, user='aos_app',
                    dbname='aos_test_379975a6f96d_ti4_test', passfile=str(passfile),
                    row_factory=dict_row) as audit:
    audit.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    for side in result['sides']:
        observed=[]
        for table,column in [('aip_budget_reservation','policy_ref'), ('aip_model_eval_budget_reservation','budget_revision_ref'), ('aip_model_judge_budget_reservation','budget_revision_ref')]:
            row=audit.execute(f"SELECT count(*) AS n,coalesce(sum(upper_bound_minor),0) AS risk FROM public.{table} WHERE org_id=%s AND project_id=%s AND {column}->>'resourceId'=%s", ('org-org','dev-project',side['budget_ref']['assetId'])).fetchone()
            observed.append({k:int(v) for k,v in row.items()})
        assert observed == side['ledger_totals']
    result['independent_after_totals_unchanged']=True
output=Path(__file__).with_name('cost-risk-reconciliation-1603-result.json')
with output.open('x') as handle: json.dump(result,handle,ensure_ascii=False,indent=2); handle.write('\n')
print(json.dumps(dict(sides=len(result['sides']),read_only=True,numeric_prices_absent=True,actual_cost_minor=None)))
