# W5CB4 BG-00bv｜正式网络动作元数据来源与当前 checker 只读审计

## 上位与当前

按 231/231-5、41 网络方案、BG-00bg/bk/bm/br/bs/bu 和 AGENTS.md 复习。当前 m1 `04f08d4b`、权威库 `aos_current_preview_20260927@a0v_116`，Host/worker/Provider关闭。仅只读代码与库；不创建假账户、不提交提案/批准，不读商城源。

## 事实与最小合法来源

- BG-00br Producer 将全局 `NetworkPolicyRevision` ObjectType 和 `aip_activate_network_policy` ActionType 的精确字段作为当前权威；当前数据库两行均0，正租户 `meta_membership` 只有 owner 1、没有第二 checker。`org-org/dev-project` 正式 Proposal/ApprovalEvent0。当前 OIDC 专用路由拒 dev token；本波未持有正式 OIDC maker/checker 身份，不做真实正向。
- 通用 `/v1/actions/types` 对固定策略 ActionType 在应用层拒绝；`a0v_115` 触发器只允许 `meta_action_type` 表 owner 操作五个固定 ID。`meta_object_type` 尚无类似 DB 保留门，`aos_runtime` 对两张全局表均有 INSERT/UPDATE 权限。通用 ObjectType 编辑器不是正式系统策略来源，不能用高权限账户或手工 SQL 临时造行以冒充正式授权。
- 最小合法注册方案：独立 a0v117 代码迁移，由表 owner 在已审定静态 schema 中精确 INSERT 两个全局元数据行，迁移前要求两行不存在、后检查字段逐项等于 Producer 合同；同步为 `NetworkPolicyRevision` ObjectType 加 owner-only DB 保留触发器，防止通用编辑器篡改。此迁移只建立可审计元数据来源，不产生 Proposal/批准/active，不应绑定任何合成账号。方案需 RED、test-only 全库克隆；若切当前仍须新的停机一致备份/零执行窗口，不能与本只读波混做。
- `openfga_api_url()` 当前为 false；当前 OIDC 设置仍有 dev token 开关为 true（既有待裁决鉴权债）。专用网络提案/决定代码均要求 `token_kind='oidc'`，dev 请求在 DB 前403；缺第二位真实当前成员时 checker 不可能正向。正式身份接入须单独依据组织/项目成员与 OIDC claim 证明，不用人工合成成员。

## 消费边界与下一波

BG-00bs 的 test-only ApprovalEvent 是决定前 Proposal 版本，批准后 Proposal 版本递增；旧 cutover 函数的版本相等校验不能复用。一次性消费需在独立后续波锁最新 Proposal/head/ApprovalEvent、核当前身份/期限/拒绝/撤回和 Egress/目标 hash，用唯一 Receipt 原子写策略。当前 a0v116 DB active trigger 必须一直保持拒绝，直到安全替换为只允许该受控消费者的数据库门。

下波 BG-00bw：先文件级方案和 RED，再只做 a0v117 精确元数据注册及 ObjectType 保留门；test-only 克隆验证普通对象仍可编辑、固定对象/ActionType runtime 不可改、Producer 精确元数据可读。当前实例迁移需独立备份/全链演练/零执行窗口；缺真实 checker 时仍不允许首链或 Host。
