# BG00FG verification · 2026-10-01

m1@4af0afb1/AOS-001021；Task W5CB4-BG00FG-20261001。仅原候选表单产品接线，无后端或schema变更。

## 命令与结果
- memory-status强一致AOS/Prime CURRENT；memory-validate GREEN（1476deliveries/1474tasks/3914events，Task前），exit0。个人eventual笔记STALE已知warning。
- RED：apps/web下 `node node_modules/vitest/vitest.mjs run src/components/aip/NetworkProposalCreationPanel.test.tsx --reporter=dot` 缺组件，exit1。
- 实现后新面板及原preview两文件：9 passed/541ms/exit0。
- 最终全量同cwd：`node node_modules/vitest/vitest.mjs run --reporter=dot > /tmp/aos-bg00fg-vitest.log 2>&1`；317 files / 2759 tests passed，17.15s，exit0。输出末尾已回读。
- `node node_modules/typescript/bin/tsc -p tsconfig.json` exit0。
- `node node_modules/vite/bin/vite.js build` exit0，407 modules，1.96s；既有大chunk warning。上述node均为/Users/ddt/.nvm/versions/node/v20.20.2/bin/node。
- `git diff --check` exit0。新代码无consumer/execute/localStorage/sessionStorage调用（rg无匹配exit1是正常检索结果）。

## 覆盖与复审
- 复用原字段与buildNetworkActivationPreview，不建第二套配置权威。GET apiGetAuthoritative禁离线缓存；POST apiPostUnqueued禁离线队列。查询缺精确引用在本地拒绝；not_attempted只允许同输入/身份快照的初次提交。
- 显式提案到期时间在未来15分钟内，点击时重校验；unknown及异常只查询。同步busy锁防同轮双击，曾提交槽突然not_attempted拒绝再提交；跨字段/身份变化丢弃迟到响应。
- URL仅保存networkPolicy/networkRevision/networkHead查询引用，无candidate/expiry/token；刷新回填引用但未查当前服务端状态前提交禁用。observed链接统一/aip/drafts?proposal=...，不宣称批准/生效，不手工消费或Run。
- React测试用API替身验证上述交互与畸形响应，不能作为真实创建/正式身份/真实审批证据。后端本波未改，不重复跑相同后端累计；BG00FF真实隔离PG证据仍独立保留。

## BrowserPilot 真实当前页面
命令 `services/aos-api/.venv/bin/python .evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-bg00fg-browser-20261001/capture.py` exit0。
独立8097/profile访问8434/aip/model-runtime；当前org-org/dev-project。新面板存在，空引用点击查询只得到“请填写精确网络策略 ID、候选修订和预期 head 版本”；提交按钮禁用。current-form.png（202426bytes）已视觉核对，snapshot.txt留存，SDK会话已关闭。没有填真实候选/注入fixture/点击写按钮。截图底部模型总览仍在读取，因此只证明目标表单禁入交互，不宣称整页核心数据就绪。

## 未完成与下一波
正式API没有通过本波重启部署，真实创建/批准/自然消费/首链仍未证明。当前真库只读，无迁移/重启、Host/worker/Provider、商城源、旧12Run、手工Run或230 L0变化。正式OS/OIDC/Owner/八配置/118到122恢复波仍待证据。Goal保障方案尚未实施，Goal状态未变。
BG00FH复核自然消费协调器与正式恢复入口缺口，先定位现有持久批准事件/outbox与消费调用路径；unknown无副作用裁决独立合同，禁止换key冒充恢复。按231首链必要范围先方案/RED/最小实现，正式材料缺只阻断对应实例。
