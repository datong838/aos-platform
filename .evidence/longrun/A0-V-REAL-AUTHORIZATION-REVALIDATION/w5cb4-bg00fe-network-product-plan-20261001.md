# BG00FE 网络配置审批产品接线开工卡

A1/E17/BG-00；Task W5CB4-BG00FE-20261001；m1@d334bd27；AOS-001019。
复习231§7.2、231-5§5/8、公共产品契约§4/8/11、412接续、现有Action收件箱/SDK、issuer合同/持久marker/独立签发链。

## 缺口与验收动作
现有SDK每次审批生成随机key；页面通用审批无法签发网络政策，approved还展示通用lease/execute。直接替换URL会让刷新后原key/body丢失，违背unknown不重发。
本波补服务端持久请求恢复的必要入口，并将网络审批嵌入既有收件箱；用户刷新仍只能查询同一发起请求，变更理由不能绕过原attempt；普通Action保持现状。不复制审批权威。

## 合同
- 新POST /networks/activation-proposals/{id}/decision-intent，复用DecideActionProposalRequest；服务端按已验证actor/scope/proposal/version生成稳定namespace key，复用execute_issuer与原marker原子占用，无新DB/schema/新状态机。
- 新GET同path?version=N：外部OIDC重验，读取API私有marker原requestHash，再构造IssuerInquiry；不需要客户端保存JWT/key/reason、不申请或重发签发。marker不存在为not_attempted（仅当前产品请求槽未占用）；损坏/权限/身份错503/403，绝不能作为可重试。已有marker即使IPC不可用也unresolved。
- marker读取复用原受保护文件解析；O_NONBLOCK防特殊文件挂住；精确schema/actor/scope/key/proposal/hash验证，不列目录/不跨actor。
- 网络页面先GET状态；仅drafted、未过期且not_attempted可提交；其余展示只读查询。提交结果未知保留在服务器，刷新读同version slot。不调用消费、通用lease/execute/withdraw/replacement。observed不宣称配置生效。
- 切换租户/登录态立即失效旧详情与请求回调；token不进入持久数据或日志。网络场景专属展示candidate目标/域名/TLS/egress引用，便于审批人审查。
- 通用Action页面与SDK语义保持，网络分支复用统一收件箱外壳/查询/timeline。
- 创建候选表单仍是preview，BG00FD查询留后续创建产品链复用；本波交付审批决策与刷新对账，不扩大到自然消费部署。

## 文件及前hash
- `services/aos-api/aos_api/aip_network_issuer_attempt.py` caa5da383cb16e31f21eacd1eff31362cbdc3bd18a0c4cfa91ab6a8e268ff47f
- `services/aos-api/aos_api/aip_network_issuer_product.py` NEW
- `services/aos-api/aos_api/routers/aip_runtime_guard_policies.py` 89056163174fd086cece6a6ebac2b8e331aa8af784f3082ea8e8a080f4dac9ae
- `services/aos-api/tests/aip/test_network_issuer_product.py` NEW
- `apps/web/src/api/aip/operations.ts` e0f81241dad2532c4c02f317a4f36cb6088867b8032bec056447f4e73847198b
- `apps/web/src/api/aipActions/networkDecision.ts` NEW
- `apps/web/src/api/aipActions/networkDecision.test.ts` NEW
- `apps/web/src/components/aip/NetworkPolicyDecisionPanel.tsx` NEW
- `apps/web/src/components/aip/NetworkPolicyDecisionPanel.test.tsx` NEW
- `apps/web/src/pages/CanonicalDraftInboxPage.tsx` ceff517e85ba4bc92a3ae472a32c26e67124187a02072a245acc1499d8f83f9a
- `apps/web/src/pages/CanonicalDraftInboxPage.test.tsx` a0b9e0826aeacbdeb965792ef53ce6d3df0f8b145ac1b830f80c077d002f9fb1

## 验证与边界
RED后最小实现，后端TLS/JWT+真实私有文件防重/刷新/身份/损坏；前端SDK与React交互契约测试（替身只证明UI合同）；相邻pytest/Vitest与TypeScript构建。
浏览器使用已读plugins/browser/kitewright/SKILL.md与engine_adapter.py的BrowserPilot兼容入口，先实测可启动；隔离端口和profile，只检查AOS页面，截图存证；不运行历史商城采集脚本。当前API缺正式身份，不能伪造批准或宣布首链。浏览器当前页面只能提供负向或只读证据；隔离测试正向注明合成fixture。
当前真实库只读、无迁移/Host/worker/Provider/商城源/旧Run。所有已有脏文件保护。回滚精确revert本波，无schema变更。
退出：专项与相邻累计、代码方案复审、浏览器证据或精确未验收说明、verification/精确commit/Delivery/CAS/AOS+Prime/413/D-waves。
下一BG00FF：创建候选产品链及自动消费协调器对接，正式部署材料与当前实例恢复独立门。

浏览器证据补充scope（独立同写者Task W5CB4-BG00FE-BROWSER-20261001）：`.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-bg00fe-browser-20261001/`。仅保存SDK脚本、快照、截图；不注入业务fixture或修改当前库。当前无网络提案时只核验真实空态，新面板真实正向验收留正式身份与提案齐备后。
