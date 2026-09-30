# W5CB4 BG00cg｜受限 API 启动器验证

## RED 与实现

基线 AOS-000935、m1 `20118c70`。按同名方案先为 `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py` 加身份文件模式/目标和 owner 预检子进程隔离测试；首次 RED 为2 failed/3 deselected（缺 `_limited_identity`/`serve_limited`），后在 `scripts/a0v_current_preview_http.py` 加独立 `--serve-limited --api-identity-file` 路径，旧 `--serve` 不改。受限路径在短寿命子进程做签名/安装/卷预检，服务进程用本机无密码连接串+PGPASSFILE路径，校验0600文件、目标端口、NOINHERIT非超级用户非BYPASSRLS、仅 runtime 成员、不能成为 owner、不能直接读受保护 Proposal 表。服务 `execve` 后不保存 owner 连接参数；缺项 fail-closed，Host/worker全关。

## 新鲜验证

- 专项 `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py --disable-warnings --tb=short`：5 passed，退出0。
- `python3.11 -m py_compile scripts/a0v_current_preview_http.py` 与精确 `git diff --check`：退出0。
- 独立 PG16 全库恢复克隆 `aos-bg00ce-isolated-pg`：test-only `aos_bg00cf_api_testonly` 的无密码身份文件和0600 pgpass 通过 `_limited_identity`/`_verify_limited_login`，输出 `LIMITED_LOGIN_GREEN aos_bg00cf_api_testonly aos_current_preview_20260927`。该克隆与当前真实卷物理隔离；正式当前角色未创建/切换。
- 09:00 当前全栈重启/只读验收另记 `w5cb4-daily-current-stack-restart-20260930.md`：当前 PG a0v117、签名预检、API/Web、八路由均可达，Host关闭。当前服务仍运行旧 `--serve` owner 路径；本代码未宣称上线。

## 限制/后续

独立 `--serve-limited` 真实启动路径尚需在克隆上完整启动并用 OIDC 读/负例回归；当前 PG 切换必须另波最新备份、克隆、零执行窗口。普通 runtime 仍可写网络 ApprovalEvent，不能把有限登录视为正式 Event 签发。签发者/Proposal不可变数据库门、第二 checker、八配置及首链仍待完成。
