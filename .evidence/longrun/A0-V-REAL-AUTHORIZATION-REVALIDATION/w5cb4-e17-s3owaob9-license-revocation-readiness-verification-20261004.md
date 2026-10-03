# E17-s3o-w-ao-b9｜License 证据撤销后绑定准入验证

## 事实与 RED

- 231-9 要求撤销后阻止新执行，BIND-1 `license_evidence_refs` 为 exact evidence/resource refs；原 `exact_assets_available` 已读同 exact EvidenceBundle 撤销事件，而 `license_evidence_available` 只查 frozen/非空摘要。当前原卷 `org-org/dev-project` 的 EvalGate/EvalContract/EvidenceBundle/Revoke 行数 `0/0/0/0`，`BEGIN READ ONLY` exit0；没有正式来源可用，不创建或冒用。
- 先修改 `tests/aip/test_e17_s3oo_capability_reader_pg.py`：可销毁 PG/独立非 owner 只读 Reader 中，frozen 且带 license_summary 的 EvidenceBundle 正向、错工作区与 dev-org 不可见，插入同 bundle/revision/hash 的 append-only revoke 后必须拒绝；撤 Reader 对 revoke 表 SELECT 必须预检失败关闭。目标测试原代码跑出 `1 failed`/exit1，失败点为撤销后仍返回 true。未触碰当前库。

## 最小实现与验证

- 只在 `aip_binding_readiness_service.py:license_evidence_available` 回读原行 `content_hash`，并查询同租户、同 bundle/revision/hash 的 `aip_evidence_bundle_revoke_event`；存在则 false。其他 ref、冻结、摘要和空列表语义不变；没有新表、迁移、API DTO 或 mock 验收。
- 目标测试修复后 `1 passed`/exit0。相邻 `test_e17_s3oo_capability_reader_pg.py`、`test_aip_binding_readiness_service.py`、`test_e17_s3ol_capability_issuer_pg.py` 合计 `31 passed`/7既有 warnings/exit0；py_compile、目标 diff check exit0。初次相邻命令误写不存在的 `test_aip_capability_binding_service.py`，pytest exit4未收集；换成真实 issuer 测试文件后通过。
- 原 `AipCapabilityBindingService.update(to_status=active)` 在写前会对当前依赖重算 readiness 且失败关闭；本修复使已撤销 License 在该重算中不再可用。该代码路径复审仅证明准入语义，尚未对生产当前库触发激活。撤销与运行之间的并发仍由 Host 当前性门独立守护。

## 当前运行门

`m1@b6e9ad5e` 代码已精确提交。随后复核既有全备 `aos-recovery/.aos-current-backup-20261004-s3owaob3/current-full.dump` SHA256 `28b356f3e7c8eb3ecf7c994e205d04ee4c2ad6f575644d3d9a8044e74c6db6f1`；该备份曾在独立 PG 完整恢复并作26/26控制摘要一致。原卷名 `aos-a0v-recovery-pg-data`、库/代码迁移同为 `a0v_135`，签名安装原预检前后 exit0：approved、4 published、runtimeBindings0。

Web/API launchd bootout 各 exit0，8080/8434/18181 均无监听；原 `aos-a0v-recovery-pg` restart exit0、`pg_isready` exit0，容器启动时刻 `2026-10-03T19:02:52.658703767Z`，仍挂原命名卷。API/Web 依次 bootstrap 各 exit0，新 PID57364/57390；18435/8080/8434 LISTEN，18181无监听。运行 HTTP：health/ready各200、旧 `/v1/tools`404/OpenAPI旧 Tool 路径0、八工作台200、技能发布页200，脚本 exit0。当前原库 `BEGIN READ ONLY`：135、Installation1、RegistryReceipt6、CapabilityBinding0、License EvidenceBundle0、Host assignment0，exit0。

In-app browser 重载 `/aip/skill-publish` 并经 AX 与截图核：org-org/dev-project，37仅已评测/发布0、正式技能发布决定/当前 Logic/模型路由策略三阻断、按钮 disabled、暂无可见电商工作台入口。截图在本轮 UI 工具输出中展示；工具未提供本地保存通道，未声称仓库内有截图文件。未点击发布/建绑定。隔离 License 正向不代表当前正式 License、六 Binding 或自然首链完成；Host/worker/Provider继续关。
