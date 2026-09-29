# W5CB4 BG-00bq｜NetworkPolicy 只读预览产品入口方案

## 上位方案复习与范围调整

按 AGENTS.md、aos-engineering-delivery、231/231-5/231-9、41 网络权威实施清单、BG-00bp 预览 API 复习。当前正租户 `meta_membership` 仅1条 owner，NetworkPolicy ObjectType/ActionType 仍0；正式独立 checker/Producer 来源不齐。按长程规则只阻断当前实例正式激活，继续可独立完成的产品配置入口。本波只让用户在 `/aip/model-runtime` 构造 HTTPS/443/无公网回退的候选并调用 BG-00bp 只读预览，展示 head/目标 hash/阻断项；不创建草稿、Action、批准或 active 策略。

## 文件级计划与测试

1. `apps/web/src/pages/s2/RuntimeNetworkPolicyPreviewPanel.test.tsx` 先 RED：固定安全边界、必填精确 Egress ref 与期望 head 版本、日期，拒绝非法/hash/旧主机；响应校验只接受 `activationAllowed=false`、恒定正式链 blockers 与合法 hash，错误/身份漂移不能显示可运行。
2. `apps/web/src/pages/s2/RuntimeNetworkPolicyPreviewPanel.tsx` 新增表单和纯构造/响应校验；唯一按钮为“只读预览阻断项”，使用 `apiPostUnqueued` 调 `POST /v1/aip/runtime-guard-policies/networks/activation-preview` 并传 `If-Match`。请求前后核 tenant/subject/auth revision 一致；错误呈不可确认，不重发。显示精确 hash 仅审计用，无批准按钮。
3. `apps/web/src/pages/s2/ModelRuntimePage.tsx` 将面板放在已有出站草稿入口之后。若当前 API/PG 无正式 Egress，显示依赖 blocker 而非就绪。
4. 专项/邻接、TypeScript 构建、Web 最新代码回读；browser-pilot 若可用截图，若不可用明确保留验收缺口；方案/代码复审、verification、m1 精确提交、01/06/D-waves/authority。

## 风险与回滚

前端表单只做交互便利，服务端合同为唯一校验；`approvalRef` 为文本必填但不构成授权。预览无事务锁、无签发身份，永远 `activationAllowed=false`；正式 Producer、checker、原子消费后续独立波。最小回滚移除面板/导入，预览 API 与 Store active 422 不变。真实库只读，Host/worker/Provider/18181 关闭，旧 Run 与商城源不触碰。
