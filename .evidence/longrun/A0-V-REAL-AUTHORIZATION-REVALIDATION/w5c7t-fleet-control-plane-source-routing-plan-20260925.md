# W5c7t Fleet 控制面来源路由计划（no-effect）

## 上位方案与现场

按 W5c7b 可信 Fleet Universe 合同、W5c7g 部署清单审计、W5c7s 优化延期裁决及 A0-V 接入恢复清单执行。真实 definition rev4 disabled，12 原 Run running；旧自然 attempt 已正式失败，绝不重发。`a0v_093/094` 未在真实库部署，Host lease 默认关闭。当前没有可证明全机 Host/worker 与禁止旧入口重启的控制面来源；本波不做真实迁移、Host 启停、closure 或商城源读取。

## 文件级清单与九步

1. 复习上述方案、`AGENTS.md`、共享 authority/Prime 投影和 m1 HEAD。
2. 本文件列出唯一变更：新增 `w5c7t-fleet-control-plane-source-routing-audit-20260925.md`、`w5c7t-fleet-control-plane-source-routing-verification-20260925.md`；不改生产代码。复核 `deploy/dev/com.aos.a0v-w5c3-runtime-host.plist`、`scripts/a0v_ecommerce_runtime_host.py`、`scripts/a0v_w5c7{c,e,f,h}_*.py`、`services/aos-api/aos_api/extension_runtime/host_lease.py` 及 worker 入口。
3. 最小实施为只读来源/覆盖审计，列出外部权威输入、仓内适配边界与缺失证明；没有可信来源时不写“可授权 adapter”。
4. 专项验证既有 Fleet/rollout 拒绝合同及真实 closure 只读门。
5. 累计回归覆盖近期 A0-V no-effect 合同；记录精确通过/跳过数。
6. 浏览器只读验收 rev4 disabled/整组停用，不点击保存、执行或待同步写队列。
7. 复审方案/代码一致性、真实库/Host 不变、全机与物理第二 Host 不被本机零进程代替。
8. verification 落盘并提交 m1；随后 CAS 更新 AOS 上下文及独立 Prime 三投影，精确提交 docs 文件。
9. 自动进入 W5c7u：在不改变真实行为前提下，盘点所有可写 worker/Owner 启动路径的 lease/fence 传递与未覆盖入口，先 plan 再实施。

## 退出与停止

未知提交边界、来源无法核验或任何零副作用读回异常均冻结；不重发旧 attempt、不手工 `run_definition`。若有源外正式控制面证据，先另起独立方案核验身份、覆盖、根、revision 与逐节点 ACK；仅时间达标不能触发旧 Run closure。230 L0 挂起，`dev-org/dev-project` 只作零 canary，m1 单写不 push。
