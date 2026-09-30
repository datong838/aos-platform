# W5CB4 BG00dt｜当前与隔离克隆的真实 actor、六实例和签名安装只读审计

## 核验范围

2026-09-30 17:56 CST，以 `a0v_current_preview_bootstrap._connection_parameters()` 和 `a0v_growth_112_successor_clone._clone_connection_parameters()` 精确连接回环当前/隔离克隆；两边连接后先 `conn.read_only=True`。只查询 `org-org/dev-project` 的 `meta_membership` 角色计数、BI 六个固定 AgentInstance 的状态计数、`bi_responsibility_plan.prepare` Receipt 数及 growth1.12 安装状态。没有输出 subject/凭据，没有读取商城源，没有数据库 mutation。

| 只读查询 | 当前 18435 | 隔离 clone 18440 |
| --- | --- | --- |
| 数据库 | `aos_current_preview_20260927` | 同名隔离克隆 |
| 六个 BI 固定实例 | `provisioning=6`，`active=0` | `provisioning=6`，`active=0` |
| 当前成员角色去重 | `owner=1` | `owner=1` |
| growth1.12 安装 | 0 | `approved=1` |
| `bi_responsibility_plan.prepare` Receipt | 0 | 0 |

复核命令（在 `aos-platform` 根目录，输出仅聚合）：

```bash
AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api:scripts services/aos-api/.venv/bin/python - <<'PY'
import psycopg
from psycopg.rows import dict_row
from a0v_current_preview_bootstrap import _connection_parameters
from a0v_growth_112_successor_clone import _clone_connection_parameters
from aos_api.ecommerce_business_investigation_aip_authority import _ROLE_BLUEPRINTS
scope=('org-org','dev-project')
ids=[item[2] for item in _ROLE_BLUEPRINTS]
for label,parameters in [('current',_connection_parameters()),('clone',_clone_connection_parameters())]:
    with psycopg.connect(**parameters,row_factory=dict_row) as conn:
        conn.read_only=True
        roles=conn.execute("SELECT status,count(*) AS n FROM aip_agent_instance WHERE org_id=%s AND project_id=%s AND instance_id=ANY(%s) GROUP BY status",(*scope,ids)).fetchall()
        members=conn.execute("SELECT role,count(DISTINCT subject) AS n FROM meta_membership WHERE org_id=%s AND project_id=%s GROUP BY role",scope).fetchall()
        receipts=conn.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND operation='bi_responsibility_plan.prepare'",scope).fetchone()['n']
        installation=conn.execute("SELECT r.state,count(*) AS n FROM bundle_installation i JOIN bundle_installation_revision r ON r.org_id=i.org_id AND r.project_id=i.project_id AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision JOIN bundle_composition_lock l ON l.org_id=r.org_id AND l.project_id=r.project_id AND l.composition_pk=r.composition_pk AND l.revision=r.lock_revision WHERE i.org_id=%s AND i.project_id=%s AND l.lock_payload::text LIKE '%%1.12.0%%' GROUP BY r.state",scope).fetchall()
        print({'target':label,'db':conn.info.dbname,'port':conn.info.port,'role_status_counts':roles,'membership_role_counts':members,'bi_prepare_receipts':receipts,'growth112_installation_state_counts':installation})
PY
```

退出码 0。辅助正式来源审计 `scripts/a0v_growth_112_formal_source_audit.py` 已将当前/clone 均判为 `formalReady=false`，八候选、Host identity/assignment 为 0。

## 判定与下一步

数据库仅能证明 `owner=1` 的成员行存在，不能从计数推出该成员持有可验证 OIDC 登录或独立 checker。两库的六实例均非 active，BG00ds 服务会在 Plan/Receipt 写前拒绝；clone 虽有 approved1.12 签名安装，也不能用伪造 Principal 或开发 actor 补正向。本波没有调用新写入口，未启 Host/worker/Provider，当前真库继续只读。

下一波补独立负向 PG 反证（权限、安装/签名漂移、幂等异 body、事务回滚）及工作台缺口呈现；合法身份和六实例正式来源齐备后再做隔离正向与产品浏览器验收。不得把本只读审计当作 Plan 建成、配置候选就绪或自然首链完成。
