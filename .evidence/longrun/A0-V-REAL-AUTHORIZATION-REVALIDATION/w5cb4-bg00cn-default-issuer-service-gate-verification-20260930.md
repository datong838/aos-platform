# W5CB4 BG00cn｜网络审批默认独立签发门验证

## 基线和 RED

接 AOS-000943，复习 231-4/231-5、BG00ci–cm，按 `w5cb4-bg00cn-independent-issuer-process-plan-20260930.md` 先做无副作用切片。当前 `decide_network_activation()` 即使无独立 issuer 仍回落普通 `db_connect`。新增 OIDC checker 负例，禁止普通 API DB 工厂被调用；初次 RED 1 failed/11 deselected，实际到达被禁止连接（退出1）。没有当前库写或正式审批请求。

## 最小实现和回归

`aip_network_policy_action_producer.py` 只在输入校验后增加 `connect_factory is None → NETWORK_ISSUER_SERVICE_REQUIRED`，并移除 network decision 的 `or db_connect` 回退。现有 maker 提案和其他 Action 路径不变。旧 `a0v_117` 合成克隆的两份 PG 测试显式注入原连接工厂，标注其仅为历史模拟验证，不是正式 issuer 服务。专项 1 passed；网络 producer/consumer 单元合计 10 passed/4 skipped、7 warnings，退出0。`py_compile`、精确 diff check 退出0。

## 风险与后续

本切片只确保 HTTP 默认网络 decision 不再经普通 API DB 连接；显式注入的接口尚未证明独立 OS 进程或真实 IdP。代码提交 `8d4c08bc` 后，签名预检再得 GREEN/a0v118/approved1/binding0；`launchctl bootout→bootstrap` 只重启 API，初次即时 curl 因启动中退出7，重试后 PID65249/8080 `/openapi.json` HTTP200。新启动日志 `CURRENT_PREVIEW_HTTP_STARTING runtimeHost=0 workersEnabled=0`、Host inactive、cron/automation worker disabled；Web8434 HTTP200、18181无监听。当前库仍 issuer NOLOGIN、HBA trust、Proposal/Event/binding0，首链待证。由于正式 OIDC/checker缺失，未通过真实 HTTP 正向调用证明路由命中本门；单测已精确证明函数默认拒绝。下一波 BG00co 继续私有进程/请求身份与凭据隔离、读回 Receipt 幂等对账；正式实例无外部 OIDC/第二 checker 时维持禁入。不读商城源、不写 dev-org、不重放旧 Run、不手工 run_definition、不 push。
