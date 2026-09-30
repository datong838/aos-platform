# W5CB4 BG00dd｜首链职责计划合法来源审计验证

## 当前签名产品事实

BG00dc 当前 receipt preflight exit 0 已核四包签名及内容哈希。对已签名增长包只读：`standard.responsibility.json` SHA256 `4f09ba944f6dfc3eea24ed9580339017278278d76aeedc333a5181992e692658`，schema 为 media responsibility template，profile STANDARD，八个 `media.*` slot，其中 `media.review` 独立且禁止合并；`ecommerce.analyst.json` SHA256 `488ff4747040f59f4270ff519efab6ca3a4df8397af232a7c4b720487263fe49`，schema 为 production profile，含 `analysis.owner` 与 `analysis.review` 两个责任 slot。两者类型、slot 和 hash 不同，不能把 media 模板当 analyst 首链职责来源。

## 正式接口边界

`CreateResponsibilityPlanRequest` 要求精确 `ResponsibilityTemplateRevision`、每个 slot 的 input/output schema ref、gate refs、assignee 及能力。STANDARD 还要求当前 profile recommendation、确认 Receipt、merge policy；Store 再验证已安装 active 的签名模板、推荐/确认/策略的精确 ref 与有效期，以及每个 assignee 的 canonical resolution Receipt 或 active AgentInstance。当前签名产品可提供 slotId、责任类型、能力和 return stage 的**候选定义**；不能推出当前人员、账号、schema/gate ref、合并裁决、批准或配置 Receipt。

`aip_responsibility_template_authority.resolve_responsibility_template` 的本地 `ecommerce.business-investigation.readonly` 特例仍返回历史 published hash；它供旧调查兼容路径，不是当前安装的签名 template ref。当前首链若借此跳过当前安装/治理门属于错误来源，不能这样做。普通已签名模板 resolver 要求安装 `active_revision`、state active、lock/包签名/artifact digest 一致；当前安装 approved@3、active 指针空，所以 media 模板精确 ref 当前也拒绝。

## 当前库只读证据与结论

`AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python` 以 `_connection_parameters()` 建 `conn.read_only=True`、精确 `org-org/dev-project` 查询 exit 0：`aip_responsibility_plan_head=0`、`aip_profile_recommendation_revision=0`、`aip_profile_confirmation_receipt=0`、`aip_merge_policy_revision=0`、`aip_assignee_resolution_receipt=0`；AgentInstance `provisioning=6`、active=0。当前无法合法形成 frozen 首链职责计划。无代码修改，RED/回归不适用；未写当前库、未读商城源、未启 Host/worker。

下波 BG00de 先复习 signed release/manifest 方案，明确 analyst 首链是否需要新版本 `ResponsibilityTemplateRevision` artifact、schema/gate/assignee 产品来源及版本迁移；只在独立 test-only 构建/测试精确签名合同，不改当前已签名树，不造假人或当前配置。正式身份/Host/Owner 缺口继续按独立安全波处理。
