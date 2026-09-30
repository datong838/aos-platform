# BG00FG 原候选表单创建接线

m1@4af0afb1 / AOS-001021，Task W5CB4-BG00FG-20261001。
复习231-5§3/5/7、公共产品契约§4/8/11、414、BG00FF持久slot合同；原RuntimeNetworkPolicyPreviewPanel与统一API client已读。

## 最小施工
- 修改apps/web/src/pages/s2/RuntimeNetworkPolicyPreviewPanel.tsx：保留现有候选字段和只读preview，加入下列创建子面板；从URL仅恢复policyId/revision/headVersion查询引用，不保存业务body/token。
- 新apps/web/src/components/aip/NetworkProposalCreationPanel.tsx：复用apiGetAuthoritative（禁离线缓存）与apiPostUnqueued（禁排队/自动重发）。查询只需精确3引用；GET not_attempted才允许提交同输入快照，显式到期时间<=15分钟；POST只能接受observed/unresolved。unknown或请求失败仅query；不能改expiry解锁同slot。
- 新对应.test.tsx：RED；fetch合同、查询前禁提交、unknown/ref变化、卸载重挂、身份变化迟到响应、observed收件箱深链、畸形响应和到期输入。替身只证明UI合同。
- query时URL仅更新三个安全引用便于刷新；当前身份仍由服务端认证，URL不带actor/租户授权。candidate/expiry变化失效旧结果，身份变化清结果并拒绝旧回调；同步busy锁防双击。提交前重查输入/身份/时效。
- 普通preview保留历史两个blocker合同；新创建成功仅称提案已创建，不表示批准/策略生效，不触发consumer/Run。当前正式API未部署新入口会失败关闭。

## 验证/证据
专项+相邻/full Vitest、TypeScript/build；BrowserPilot独立8097/profile只浏览当前8434模型运行页，空输入提交禁用截图；不向当前库注入提案、不点写按钮，不声称真实正向首链。证据目录w5cb4-bg00fg-browser-20261001/。
复审、verification、精确commit、Receipt/CAS、415与D-waves后下一波。

## 边界与后续
无副作用证明后释放/恢复unknown的产品合同仍未实现，不能用换key解决。本波不做真库迁移/重启、Host/worker/Provider、商城源、旧12Run、手工Run或230 L0。正式身份与部署及自然消费独立待验收。下一BG00FH复核自然消费协调器与正式恢复入口的缺口，按证据选择首链必要实现，不全量扩展。
