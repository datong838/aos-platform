# W5CB4 BG00cn｜独立网络审批签发进程文件级方案

## 上位依据与当前现场

复习 231-4 非 owner 专用角色/最小表权限、231-5 真实人工审批与幂等、BG00ci 正式身份只读审计及 BG00cj–cm 的 DB/HBA/真实登录证据。当前代码/库均 a0v118；克隆已证明独立 issuer TCP/SCRAM 事务可插网络 Event，但当前实例 HBA 仍 trust、issuer NOLOGIN，API 为 aos_app，正式 OIDC/第二 checker 缺失。`decide_network_activation()` 当前默认仍直接用普通 `db_connect`。克隆真实 issuer 读取 `pg_hba_file_rules` 被 SQLSTATE 42501 拒绝，因此不能让 issuer 自己证明 HBA 安全，须独立部署预检。

## 最小施工顺序

1. 先写 RED：生产默认网络 `decide` 不能落到普通 API 数据库连接；只有显式注入独立签发接口才能请求签发。对空接口、同进程携带 issuer 密码、未验外部 OIDC/第二 checker、跨租户/旧 Proposal/重复 key、未知结果重发分别失败封闭。现有其他 Action 和网络 maker 提案不改变。
2. `services/aos-api/aos_api/aip_network_policy_action_producer.py` 与 `routers/aip_runtime_guard_policies.py`：网络审批入口调用专门 issuer client。API 只传经过外部 OIDC 原始凭据或可重验的签名断言、精确 tenant/proposal/hash/idempotency，不传 DB 凭据；发起方不能自行宣称 checker。未知响应只能按 idempotency 读签发 Receipt，不重发 INSERT。
3. 新增独立签发进程模块及 `services/aos-api/tests/aip/` 专项：进程以不同 OS 身份运行，只有它可读 issuer 0600 凭据；私有 socket/peer 鉴别、请求大小/时限、禁止任意 SQL/任意 Action；进程自己重新验证外部 OIDC issuer/audience/JWKS、当前 meta_membership 和 Proposal 的 maker/checker、preview/hash/预算/安装代次，事务内执行现有 `AipActionStore.decide`，只允许 `session_user=issuer/current_user=runtime`。错误与未知结果保留精确幂等对账入口。
4. 启动部署门与进程分离：更高权限的只读 HBA 预检使用 BG00cl gate，核克隆/目标的精确数据库、卷、角色、PG权限、签名 Receipt 和进程 OS 身份；通过后交付只读签名/权限受限的启动证明，进程不得自行授予 LOGIN/CONNECT。当前本机只有同一用户/当前 API owner 路径，若无法提供 OS 隔离或正式 IdP，则先完成默认失败封闭与接口契约，隔离克隆验证，不启动当前进程。
5. 方案与代码双复审、专项/邻接回归、适用时浏览器、verification、m1 精确提交、AOS/Prime 同步后进入下波。当前实例切换另需一致备份/全链克隆/零执行窗口，不能借本波改 HBA/角色或重启 Host。

## 文件边界与止损

初始切片拟改 `services/aos-api/aos_api/aip_network_policy_action_producer.py`、相关 router 与测试；如接口服务尚无合法 OS/IdP 来源，只实现默认拒绝和合同测试，不存 DB 密码于 API 环境或源码。任何当前库写、dev-org 写、商城源读取、旧 Run 回放、手工 run_definition、Host/worker/Provider 启动和 push 禁止。克隆正例不等于当前正式 checker/首链完成。
