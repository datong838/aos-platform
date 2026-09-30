# W5CB4 BG00cy｜当前职责来源核验

- 基线 `m1@31bffc82`、`AOS-000954`，任务 Receipt `W5CB4-BG00CY-20260930`，方案见同名 plan。
- `AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python` 使用 `_connection_parameters()` 及 `psycopg` 只读连接核当前库，退出 0：唯一安装 head `active_revision=NULL`，最新修订 3 `approved`；`aip_responsibility_plan_head=0`，`aip_profile_recommendation_revision=0`，`aip_profile_confirmation_receipt=0`，`aip_merge_policy_revision=0`；六个 `aip_agent_instance` 全是 `provisioning`，非 active。
- Registry 只读精确 artifact 查询退出 0：`solution.ecommerce.growth@1.11.0` 为 published 且 signature 非空，standard 责任模板 artifact digest 为 `sha256:4f09ba944f6dfc3eea24ed9580339017278278d76aeedc333a5181992e692658`。这只证明 Registry 制品记录，不证明当前安装已 active。
- `InstalledProductionProfileResolver(connect_factory=read_only)` 对该 artifact 的精确 `ResponsibilityTemplateRevision` ref、安装修订 3 的核验退出 0，返回 `false`。现有代码要求 `active_revision=ref.revision` 且安装状态 `active`、lock/签名/摘要一致；当前 head 为空，拒绝符合 231-3。231-3 规定 runtime-apply/verify 在配置前，故不构成必然状态机死环；当前实例仍因 Host/Owner 门未闭合无法推进该状态转换。
- 方案复审：没有放宽模板 resolver、添加本地假来源、写当前库、改预算/审批/运行门或触发业务链。本波无代码变更，RED/代码回归及浏览器截图不适用；结论仅是当前来源审计。
- 未完成：正式 Host 独立身份与 assignment/Owner、第二 checker、八类配置 active 来源、AgentInstance 激活与自然首链。下一波从 Host 精确身份/assignment 的可信来源和产品入口做文件级方案与最小独立切片；缺外部授权时保持该实例禁入并推进可独立的产品配置代码。
