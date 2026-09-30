# W5CB4 BG00cm｜隔离克隆 issuer 真实 SCRAM 登录验证

## 基线与隔离

接 AOS-000942/m1 `5993e07d`。仅使用 `colima-aos-a0v-test-only/aos-bg00ck-isolated-pg`、独立卷 `aos-bg00ck-isolated-pg-data`、127.0.0.1:18437、库 `aos_current_preview_20260927@a0v_118`。操作前回读 issuer `NOLOGIN NOINHERIT`、非 owner、是 `aos_runtime` 成员、CONNECT=false；HBA local/127/::1 通用 trust。当前权威卷与 API/Web 未停改。

## 配置与测试证据

克隆原 HBA 复制到私有 `/Users/ddt/work/projects/ai_agent/.aos-bg00cm-issuer-qTLrIa/hba-before.conf`，目录0700、文件0600，SHA256 `af0fdb739b67d1a552cd82c19311b813e753d4f651a61e6b563f48b55dca5e74`。只给克隆在宽泛 trust 前置目标库＋issuer 的 local、IPv4/IPv6 三条 SCRAM；reload 退出0，`pg_hba_file_rules` 错误0，BG00cl gate 从 `ISSUER_HBA_UNSAFE` 退出2变为 `ISSUER_HBA_GATE_GREEN` 退出0。随机凭据仅写私有0600 `issuer.pgpass`，未输出；克隆 `ALTER ROLE ... LOGIN PASSWORD`、精确 `GRANT CONNECT` 均退出0。

宿主经真实 TCP/18437 以错误密码连接被拒绝；正确密码连接的 `session_user=current_user=aos_network_approval_issuer`、`rolsuper=false`、非 `aos_app` 成员；事务内 `SET LOCAL ROLE aos_runtime` 后 `session_user=issuer/current_user=aos_runtime`，精确 org-org/dev-project GUC。克隆用 admin 单独提交一条 `bg00cm-isolated-*` 测试 Proposal（跨连接可见所需，保留于克隆）；真实 issuer 登录会话内插入网络 ApprovalEvent 并更新 Proposal 到 approved/version2 均成功，然后 `ROLLBACK`。再回读克隆 Proposal `drafted/version1`、该 Event 0。issuer 以真实登录试图另建 maker Proposal 被 `NETWORK_PROPOSAL_MAKER_ROLE_REQUIRED` 拒绝。可重复专项 `test_a0v_network_issuer_real_login_pg.py` 1 passed。

BG00cl 原 trust 负例改指另一个未改动隔离克隆 `aos-bg00ce-isolated-pg`，与 BG00cj DB 门邻接 8 passed；真实 SCRAM 专项独立 1 passed，均7 warnings/退出0。`py_compile`、精确 diff check 退出0。此波未运行网络生产 API 决策，未创建真实 checker/授权，测试 Proposal 仅留在克隆，不是当前库业务事实。

## 当前实例与风险

当前权威库只读回读 `aos_current_preview_20260927@a0v_118`、issuer `NOLOGIN/NOINHERIT/NOSUPERUSER`、Proposal/Event/binding=0；API `/openapi.json`、Web `/aip/skill-publish` HTTP200，18181无监听。当前 HBA 仍 trust、没有外部 OIDC/第二 checker 或独立签发进程；不能启当前 issuer/Host/worker/Provider，首链仍待证。下一波 BG00cn 把签发逻辑隔离到独立进程，验证身份、幂等/失败重试和凭据不进入 API；正式当前库切换再走独立备份/克隆/零执行门。无商城源读取、dev-org 写、旧 Run 回放、手工 run_definition、push。
