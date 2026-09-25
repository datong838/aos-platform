# W5c7b 可信 Fleet Universe 合同设计验证（2026-09-25）

## 第 1/9～4/9 步：上位方案与设计

- 复习 231/231-9、W5c5h/W5c6m/W5c7a、`a0v_093/094` 与 Host opt-in；方案 `e978239d` 先提交。
- 仅新增设计证据 `62ba49b6`：可信 universe 需由唯一受管部署控制平面给出签名、限时、不可变 revision、覆盖所有 machine/cluster/namespace/launch surface/Host identity/DB role OID 的清单，并可追溯资产与部署 revision。未知/离线/未受管启动入口不得被“零观测”抹去。
- cutover 顺序锁定为：隔离验证 migration 与全 Owner/worker 同事务 fence→真实迁移独立审批/回滚→新入口强制 lease/fence→旧入口禁止重启/撤权和 stop/drain→全节点 ACK、进程/容器/连接与第二 Host=0 读回→Fresh Owner 单事务及独立 closure plan/key。本文**仅设计**，未迁移真实库、未停止 Host、未执行 closure。

## 第 5/9～7/9 步：回归、浏览器、复审

- W5c5k–z/W5c6a–z、JDBC、探针合同及 Host topology/closure 合计 `134 passed`；测试 PG 已停。
- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`，运行状态 `数据组已停用`；待同步写操作 1 未冲刷，未保存/运行。
- 真实 closure 门仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格时钟须晚于 `2026-09-25T20:00:04.800482+00:00`。
- 方案/代码一致性：现有目录、Host lease opt-in、`a0v_093/094` 迁移代码及隔离 PG fence 不等于完整部署；真实 DB 仍 `a0v_092`。签名 universe、旧入口禁止重启、全节点读回、全路径 worker fence 与 Fresh Owner closure 均未落实。任何缺口都保持 fail closed。

## 第 8/9～9/9 步：记忆与下一波

- 本文件提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回；提交见 docs context69。
- 下一波 W5c7c：先方案，选可独立验证的 fail-closed universe 纯合同/解析器切片；无可信现网清单则仅 isolated/no-effect，不接真实 closure。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
