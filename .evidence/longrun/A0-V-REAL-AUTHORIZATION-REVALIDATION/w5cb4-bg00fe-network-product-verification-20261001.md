# BG00FE verification · 2026-10-01

## 范围与基线
m1@d334bd27；AOS-001019；Task W5CB4-BG00FE-20261001 与 W5CB4-BG00FE-BROWSER-20261001。同一写者；无push，无当前真实库写入/迁移/重启，无Host/worker/Provider/商城源/旧Run。
网络审批嵌入原收件箱；服务端稳定产品请求槽、原marker读取与只读查询。不是新增审批权威；not_attempted仅表示当前产品请求槽不存在，不证明其他渠道没有历史执行。

## RED / 实现 / 验证
- 后端RED缺新模块ImportError，exit2；前端RED缺模块exit1。首次pnpm命令因node不在PATH失败，改用现有Node绝对路径；无依赖升级。
- 后端初步27 passed/15.05s；最终相邻累计60 passed/21.53s/exit0：
```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_issuer_product.py services/aos-api/tests/aip/test_network_issuer_application.py services/aos-api/tests/aip/test_aip_network_issuer_attempt.py services/aos-api/tests/aip/test_network_consumer_attempt.py services/aos-api/tests/aip/test_network_issuer_client.py services/aos-api/tests/aip/test_network_proposal_reconcile_pg.py --tb=short --show-capture=no
```
- 前端初步专项25 passed/633ms，随后补真实unmount/remount和observed用例，最终全量包含所有新用例。cwd apps/web：
```sh
/Users/ddt/.nvm/versions/node/v20.20.2/bin/node node_modules/vitest/vitest.mjs run --reporter=dot
```
最终316 files / 2754 tests passed，16.44s，exit0；session27816完成输出已回读。既有React act/Router警告存在。
- 同cwd `node node_modules/typescript/bin/tsc -p tsconfig.json` exit0；`node node_modules/vite/bin/vite.js build` exit0、406modules、1.97s，有既有chunk-size警告。node均使用上述绝对路径。构建后仅有效期展示/点击时校验与测试补充，最终Vitest覆盖最终文件。
- `git diff --check` exit0；memory-status强一致AOS/Prime CURRENT；memory-validate GREEN（1473deliveries/1473tasks/3908events，交付前）。个人eventual笔记STALE为已知warning，不写个人memory。

## 复审与覆盖
- OIDC二次验证通过后读取精确actor/scope/key的原requestHash；marker损坏、跨身份、符号链接、FIFO拒绝，不回落为未尝试。O_NONBLOCK避免FIFO阻塞。
- POST复用原issuer原子占用，刷新GET只查询；同请求再次POST走原inquiry，修改理由冲突不再次dispatch。稳定key仅用于产品接口，不声称覆盖历史任意key。
- React同步busy锁、unknown禁重发、卸载重挂读服务端、身份变化失效和迟到响应丢弃；observed显示事件，不显示已生效。网络分支禁通用lease/execute/withdraw/copy，普通Action累计保持通过。
- 后端新专项真实私有文件、HTTPS/JWT；IPC capture仅验证派发合同，不代表真实签发。前端SDK/React替身只证明交互合同。相邻PG测试使用独立测试库，非当前正式安装验收。

## BrowserPilot 真实只读证据
`w5cb4-bg00fe-browser-20261001/capture.py` 使用仓库BrowserPilot兼容SDK、独立8097端口/profile，访问当前8434/aip/drafts，未手写CDP。首次等待标题过早，只得loading，保留initial-loading.png/txt，不算通过；改等待终态selector后exit0，current-inbox.png与snapshot.txt显示org-org/dev-project、0条受控动作、真实空态正常。截图已视觉复核，SDK会话已关闭。未注入提案/fixture、未点业务写按钮。
该结果只证明当前审批台可读和空态；当前API尚未正式部署本波入口，新面板真实正向未验收。BrowserPilot已恢复可用，后续不能继续沿用“工具不可用”的旧判断。

## 未完成与下一波
正式OS/OIDC材料、受限API部署、当前a0v118到代码a0v122恢复波、配置Owner/Host与自然首链仍待证据，交付状态仍E16禁入/E17首链pending。Goal保障方案未实施，未改Goal状态。
BG00FF从候选创建产品链入手：复核现有preview、BG00FD原请求查询和服务端持久引用，先文件级方案/RED，再最小接线；自动消费协调器按正式授权边界推进，禁止手工消费/Run。
