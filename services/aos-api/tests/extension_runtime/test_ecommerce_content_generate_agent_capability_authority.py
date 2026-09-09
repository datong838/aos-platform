import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.aip_agent_registry_contracts import (
    AgentInstanceStatus,
    CapabilityReadiness,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    canonical_hash as production_contract_canonical_hash,
)
from aos_api.aip_production_contracts import (
    AssigneeKind,
    BriefLifecycle,
    ContractReadiness,
    Coverage,
)
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _ref(resource_type: str, resource_id: str, digest: str) -> InvestigationExactRef:
    return InvestigationExactRef.model_validate(
        {
            "resourceType": resource_type,
            "resourceId": resource_id,
            "revision": 1,
            "contentHash": "sha256:" + digest,
        }
    )


def _plan_content(
    *, agent_id: str = "agent-1", capability_id: str = "capability-1"
) -> dict:
    schema = {
        "resourceType": "Schema",
        "resourceId": "schema://content/generate",
        "revision": "1",
        "authority": "aip",
    }
    return {
        "profile": "ecommerce-content",
        "templateRef": {
            "resourceType": "ResponsibilityTemplateRevision",
            "resourceId": "ecommerce-content",
            "revision": 1,
            "contentHash": HASH_A,
        },
        "slots": [
            {
                "slotId": "content.generate",
                "responsibilityType": "content_generation",
                "requiredCapabilityIds": [capability_id],
                "inputSchemaRef": schema,
                "outputSchemaRef": schema,
                "gateRefs": [],
                "returnStage": "content.review",
                "assignee": {
                    "kind": "agent_instance",
                    "resourceId": agent_id,
                    "version": 1,
                },
                "assigneeResolutionReceiptId": None,
            }
        ],
        "mergeDecisions": [],
        "profileRecommendationRef": None,
        "profileConfirmationId": None,
        "mergePolicyRef": None,
        "mergeDecisionReceiptIds": [],
    }


class Transaction:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.agent_row = {"owner": "agent"}
        self.head = {"current_revision": 1, "version": 1}
        content = _plan_content()
        self.plan_row = {
            "profile": content["profile"],
            "template_ref": content["templateRef"],
            "slots": content["slots"],
            "merge_decisions": content["mergeDecisions"],
            "profile_recommendation_ref": content["profileRecommendationRef"],
            "profile_confirmation_id": content["profileConfirmationId"],
            "merge_policy_ref": content["mergePolicyRef"],
            "merge_decision_receipt_ids": content["mergeDecisionReceiptIds"],
            "content_hash": production_contract_canonical_hash(content),
            "lifecycle": "frozen",
        }
        self.capability_row = {
            "owner": "capability",
            "latest_published_revision": 1,
            "required_data_refs": [],
            "required_tool_refs": [],
        }

    def execute(self, query, _params):
        self.queries.append(query)
        value = (
            self.agent_row
            if "aip_agent_instance" in query
            else self.head
            if "aip_responsibility_plan_head" in query
            else self.plan_row
            if "aip_responsibility_plan_revision" in query
            else self.capability_row
        )

        class Result:
            def fetchone(self):
                return value

        return Result()


def _owners(monkeypatch):
    agent = SimpleNamespace(
        instance_id="agent-1",
        version=1,
        status=AgentInstanceStatus.ACTIVE,
        instance_ref=SimpleNamespace(content_hash=HASH_A),
    )
    slot = SimpleNamespace(
        assignee=SimpleNamespace(
            kind=AssigneeKind.AGENT_INSTANCE,
            resource_id="agent-1",
            version=1,
        ),
        required_capability_ids=["capability-1"],
    )
    plan = SimpleNamespace(
        plan_id="responsibility-1",
        revision=1,
        version=1,
        content_hash=production_contract_canonical_hash(_plan_content()),
        lifecycle=BriefLifecycle.FROZEN,
        readiness=ContractReadiness.READY,
        coverage=Coverage.COMPLETE,
        blockers=[],
        uncovered_slots=[],
        slots=[slot],
    )
    capability = SimpleNamespace(
        capability_id="capability-1",
        revision=1,
        content_hash=HASH_C,
        lifecycle=TemplateLifecycle.PUBLISHED,
        readiness=CapabilityReadiness.AVAILABLE,
        readiness_reasons=[],
        required_data_refs=[],
        required_tool_refs=[],
    )
    monkeypatch.setattr(
        AipAgentRegistryStore,
        "_instance_from_row",
        classmethod(lambda _cls, _scope, _row: agent),
    )
    monkeypatch.setattr(
        AipProductionContractStore,
        "get_responsibility_plan",
        lambda _self, _scope, _plan_id, _revision, conn: plan,
    )
    monkeypatch.setattr(
        AipCapabilityRegistry,
        "_from_row",
        staticmethod(lambda _row: capability),
    )
    return agent, plan, capability


def _authorities():
    return {
        "agent_instance": _ref("AgentInstanceRevision", "agent-1", HASH_A),
        "responsibility_plan": _ref(
            "ResponsibilityPlanRevision",
            "responsibility-1",
            production_contract_canonical_hash(_plan_content()),
        ),
        "capability": _ref("CapabilityRevision", "capability-1", HASH_C),
    }


def test_content_generate_accepts_current_agent_plan_and_capability(monkeypatch):
    _owners(monkeypatch)
    transaction = Transaction()

    ContentGenerateHostService._agent_capability_authority(
        transaction, SCOPE, _authorities()
    )

    assert all("public." in query for query in transaction.queries)
    assert sum("FOR SHARE" in query for query in transaction.queries) == 2
    assert "max(candidate.revision)" in transaction.queries[-1]


@pytest.mark.parametrize(
    "drift",
    [
        "agent_status",
        "agent_version",
        "agent_hash",
        "head_bool",
        "plan_current",
        "plan_lifecycle",
        "plan_readiness",
        "plan_slot_agent",
        "plan_slot_capability",
        "plan_raw_bool",
        "capability_hash",
        "capability_lifecycle",
        "capability_readiness",
        "capability_reasons",
        "capability_latest",
        "capability_data_bool",
        "capability_tool_whitespace",
    ],
)
def test_content_generate_rejects_agent_plan_or_capability_drift(monkeypatch, drift):
    agent, plan, capability = _owners(monkeypatch)
    transaction = Transaction()
    authorities = _authorities()
    if drift == "agent_status":
        agent.status = AgentInstanceStatus.SUSPENDED
    elif drift == "agent_version":
        agent.version = 2
    elif drift == "agent_hash":
        authorities["agent_instance"] = _ref(
            "AgentInstanceRevision", "agent-1", HASH_B
        )
    elif drift == "head_bool":
        transaction.head["version"] = True
    elif drift == "plan_current":
        transaction.head["current_revision"] = 2
    elif drift == "plan_lifecycle":
        plan.lifecycle = BriefLifecycle.DRAFT
    elif drift == "plan_readiness":
        plan.readiness = ContractReadiness.BLOCKED
    elif drift == "plan_slot_agent":
        plan.slots[0].assignee.resource_id = "agent-2"
    elif drift == "plan_slot_capability":
        plan.slots[0].required_capability_ids = ["capability-2"]
    elif drift == "plan_raw_bool":
        transaction.plan_row["slots"][0]["assignee"]["version"] = True
    elif drift == "capability_hash":
        authorities["capability"] = _ref("CapabilityRevision", "capability-1", HASH_A)
    elif drift == "capability_lifecycle":
        capability.lifecycle = TemplateLifecycle.DEPRECATED
    elif drift == "capability_readiness":
        capability.readiness = CapabilityReadiness.DEGRADED
    elif drift == "capability_reasons":
        capability.readiness_reasons = ["blocked"]
    elif drift == "capability_latest":
        transaction.capability_row["latest_published_revision"] = 2
    elif drift == "capability_data_bool":
        transaction.capability_row["required_data_refs"] = [
            {"assetType": "EvalDatasetRevision", "assetId": "data-1", "revision": True, "contentHash": HASH_A}
        ]
        capability.required_data_refs = [
            VersionedAssetRef(assetType="EvalDatasetRevision", assetId="data-1", revision=1, contentHash=HASH_A)
        ]
    elif drift == "capability_tool_whitespace":
        transaction.capability_row["required_tool_refs"] = [
            {"assetType": "EvidenceBundleRevision", "assetId": " tool-1 ", "revision": 1, "contentHash": HASH_A}
        ]
        capability.required_tool_refs = [
            VersionedAssetRef(assetType="EvidenceBundleRevision", assetId="tool-1", revision=1, contentHash=HASH_A)
        ]

    with pytest.raises(ValueError):
        ContentGenerateHostService._agent_capability_authority(
            transaction, SCOPE, authorities
        )


def test_content_generate_reads_canonical_public_agent_plan_and_capability():
    suffix = uuid4().hex[:10]
    template_id = f"content-template-{suffix}"
    agent_id = f"content-agent-{suffix}"
    skill_id = f"content-skill-{suffix}"
    skill_binding_id = f"content-skill-binding-{suffix}"
    capability_binding_id = f"content-capability-binding-{suffix}"
    capability_id = f"content.generate.{suffix}"
    plan_id = f"content-plan-{suffix}"
    exact = lambda kind, identity, digest: {
        "assetType": kind,
        "assetId": identity,
        "revision": 1,
        "contentHash": digest,
    }
    source = {
        "resourceType": "SolutionPack",
        "resourceId": "ecommerce-growth",
        "revision": "1",
        "authority": "asset-registry",
    }
    plan_content = _plan_content(agent_id=agent_id, capability_id=capability_id)
    slot = plan_content["slots"][0]
    plan_hash = production_contract_canonical_hash(plan_content)
    bool_plan_id = f"content-plan-bool-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (SCOPE.org_id, "栖月汇"),
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name)
                 VALUES(%s,%s,%s) ON CONFLICT DO NOTHING""",
            (*SCOPE.key, "默认工作区"),
        )
        conn.execute(
            """INSERT INTO public.aip_agent_template_revision
                 (template_id,revision,display_name,role_key,lifecycle,source_ref,
                  source_license,manifest,content_hash,created_by)
                 VALUES(%s,1,'内容官','content_officer','published',%s::jsonb,
                        'internal','{}'::jsonb,%s,'pytest')""",
            (template_id, json.dumps(source), HASH_A),
        )
        conn.execute(
            """INSERT INTO public.aip_agent_instance
                 (org_id,project_id,instance_id,template_id,template_revision,status,
                  overlay,version,created_by)
                 VALUES(%s,%s,%s,%s,1,'active','{}'::jsonb,1,'pytest')""",
            (*SCOPE.key, agent_id, template_id),
        )
        refs = json.dumps(exact("SchemaRevision", "content.generate", HASH_A))
        conn.execute(
            """INSERT INTO public.aip_capability_revision
                 (capability_id,revision,display_name,lifecycle,parent_ref,aliases,
                  input_schema_ref,output_schema_ref,risk_level,required_data_refs,
                  required_tool_refs,required_capability_refs,eval_pack_ref,
                  memory_policy_ref,handoff_policy_ref,effect_review_schema_ref,
                  license_policy_ref,readiness_policy_ref,readiness,readiness_reasons,
                  source_ref,source_license,content_hash,created_by)
                 VALUES(%s,1,'内容生成','published',NULL,'[]'::jsonb,%s::jsonb,%s::jsonb,
                        'medium','[]'::jsonb,'[]'::jsonb,'[]'::jsonb,NULL,%s::jsonb,
                        %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,'available','[]'::jsonb,
                        %s::jsonb,'internal',%s,'pytest')""",
            (capability_id, refs, refs, refs, refs, refs, refs, refs, json.dumps(source), HASH_C),
        )
        conn.execute(
            """INSERT INTO public.aip_skill_template_revision
                 (skill_id,revision,canonical_logic_id,lifecycle,input_schema,output_schema,
                  tool_allowlist,required_capabilities,risk_level,memory_policy_ref,
                  handoff_policy_ref,source_ref,source_license,content_hash,created_by)
                 VALUES(%s,1,%s,'draft','{}'::jsonb,'{}'::jsonb,'[]'::jsonb,
                        '[]'::jsonb,'low','{}'::jsonb,'{}'::jsonb,%s::jsonb,
                        'internal',%s,'pytest')""",
            (skill_id, f"logic.{skill_id}", json.dumps(source), HASH_B),
        )
        conn.execute(
            """INSERT INTO public.aip_capability_binding
                 (org_id,project_id,binding_id,capability_ref,secret_ref,health,
                  network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,
                  status,version,operational_readiness,allow_degraded,
                  dependency_snapshot_hash,last_evaluated_at,readiness_expires_at,observed_at)
                 VALUES(%s,%s,%s,%s::jsonb,'secret://pytest/content','healthy',
                        'network-1','quota-1',30000,1,'active',1,'available',FALSE,
                        %s,NOW(),NOW()+INTERVAL '1 hour',NOW())""",
            (
                *SCOPE.key,
                capability_binding_id,
                json.dumps(exact("CapabilityRevision", capability_id, HASH_C)),
                HASH_A,
            ),
        )
        conn.execute(
            """INSERT INTO public.aip_skill_binding
                 (org_id,project_id,binding_id,instance_id,skill_id,skill_revision,
                  capability_refs,budget_policy_ref,status,version)
                 VALUES(%s,%s,%s,%s,%s,1,%s::jsonb,'{}'::jsonb,'active',1)""",
            (
                *SCOPE.key,
                skill_binding_id,
                agent_id,
                skill_id,
                json.dumps([capability_binding_id]),
            ),
        )
        conn.execute(
            """INSERT INTO public.aip_responsibility_plan_head
                 (org_id,project_id,plan_id,current_revision,version)
                 VALUES(%s,%s,%s,1,1)""",
            (*SCOPE.key, plan_id),
        )
        conn.execute(
            """INSERT INTO public.aip_responsibility_plan_revision
                 (org_id,project_id,plan_id,revision,profile,template_ref,slots,
                  merge_decisions,content_hash,lifecycle,created_by)
                 VALUES(%s,%s,%s,1,'ecommerce-content',%s::jsonb,%s::jsonb,
                        '[]'::jsonb,%s,'frozen','pytest')""",
            (
                *SCOPE.key,
                plan_id,
                json.dumps(
                    {
                        "resourceType": "ResponsibilityTemplateRevision",
                        "resourceId": "ecommerce-content",
                        "revision": 1,
                        "contentHash": HASH_A,
                    }
                ),
                json.dumps([slot]),
                plan_hash,
            ),
        )
        bool_slot = json.loads(json.dumps(slot))
        bool_slot["assignee"]["version"] = True
        conn.execute(
            """INSERT INTO public.aip_responsibility_plan_head
                 (org_id,project_id,plan_id,current_revision,version)
                 VALUES(%s,%s,%s,1,1)""",
            (*SCOPE.key, bool_plan_id),
        )
        conn.execute(
            """INSERT INTO public.aip_responsibility_plan_revision
                 (org_id,project_id,plan_id,revision,profile,template_ref,slots,
                  merge_decisions,content_hash,lifecycle,created_by)
                 VALUES(%s,%s,%s,1,'ecommerce-content',%s::jsonb,%s::jsonb,
                        '[]'::jsonb,%s,'frozen','pytest')""",
            (
                *SCOPE.key,
                bool_plan_id,
                json.dumps(plan_content["templateRef"]),
                json.dumps([bool_slot]),
                plan_hash,
            ),
        )
        agent_row = conn.execute(
            """SELECT i.*,t.content_hash FROM public.aip_agent_instance i
                 JOIN public.aip_agent_template_revision t
                   ON t.template_id=i.template_id AND t.revision=i.template_revision
                WHERE i.org_id=%s AND i.project_id=%s AND i.instance_id=%s""",
            (*SCOPE.key, agent_id),
        ).fetchone()
        agent = AipAgentRegistryStore._instance_from_row(SCOPE, agent_row)
        for table in (
            "aip_agent_instance",
            "aip_agent_template_revision",
            "aip_responsibility_plan_head",
            "aip_responsibility_plan_revision",
            "aip_skill_binding",
            "aip_capability_binding",
            "aip_capability_revision",
        ):
            conn.execute(f"CREATE TEMP TABLE {table} (LIKE public.{table})")
        ContentGenerateHostService._agent_capability_authority(
            HostTransaction(conn),
            SCOPE,
            {
                "agent_instance": _ref(
                    "AgentInstanceRevision", agent_id, agent.instance_ref.content_hash
                ),
                "responsibility_plan": _ref(
                    "ResponsibilityPlanRevision", plan_id, plan_hash
                ),
                "capability": _ref("CapabilityRevision", capability_id, HASH_C),
            },
        )
        with pytest.raises(ValueError, match="ResponsibilityPlan"):
            ContentGenerateHostService._agent_capability_authority(
                HostTransaction(conn),
                SCOPE,
                {
                    "agent_instance": _ref(
                        "AgentInstanceRevision", agent_id, agent.instance_ref.content_hash
                    ),
                    "responsibility_plan": _ref(
                        "ResponsibilityPlanRevision", bool_plan_id, plan_hash
                    ),
                    "capability": _ref("CapabilityRevision", capability_id, HASH_C),
                },
            )
        conn.rollback()
