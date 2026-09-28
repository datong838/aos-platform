# W5CB4 E17-s｜三身份凭据预检至连接期代次门 verification

## 实现与范围

`runtime_connections._runtime_file_dsns` 从同一个 0600、当前用户所有、非 symlink 文件 descriptor 读取三身份，并核对读取前后无密钥代次 `(device,inode,size,mtime_ns,ctime_ns)`；只在显式请求时返回该代次。`a0v_current_runtime_host_preflight` 在三身份真实连接后再核文件未改变，并在 GREEN 中给出代次。API 当前 Host 启动门仅在签名、scope 和 API 物理数据库 authority 匹配后 pin 路径与代次；后续 runtime/directory/web/lease 连接每次读取都会检查，漂移固定 `runtime credential reference is invalid`，不回退旧 DSN。代次只作为内部预检消息，不包含密码、DSN、可离线猜测的内容摘要；轮换须停 Host 并重启完整预检。

## 本轮证据

| 检查 | 命令与结果 |
| --- | --- |
| RED | `python -m pytest -q -o log_cli=false services/aos-api/tests/extension_runtime/test_runtime_connections.py -k pinned_credential_generation --tb=short` 退出 1，3 failed：旧实现没有 `with_generation`，替换/重写/换路径无代次门。 |
| GREEN 专项 | 同目录 `test_runtime_connections.py`、`test_a0v_current_runtime_host_preflight.py`、`test_production_runtime.py`：退出 0，61 passed，含文件原子替换、原位重写、路径改动、子进程预检后代次变更、API pin 失败封闭。 |
| 邻接累计 | 上述加 `test_ui_read_production_wiring.py`、`test_runtime_startup_composition.py`、`test_runtime_installations_api.py`、`test_a0v_ecommerce_runtime_host.py`、`test_a0v_current_preview_http.py`：退出 0，133 passed。`compileall` 与 `git diff --check` 退出 0。 |
| 真实缺身份门 | `scripts/a0v_current_runtime_host_preflight.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 无正式凭据引用：预期退出 2，`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。未使用旧文件或预览超级账号正向验收。 |
| 当前预览 | 用当前签名 Receipt 和代码重启 API；日志 `startup_extension_runtime_host_inactive code=DISABLED`，8080 `/v1/health`、`/v1/ready` 和 8434 `/aip/skill-publish` HTTP 200，18181 无监听。`docker --context colima-aos-extension inspect aos-a0v-recovery-pg`：running true、`aos-a0v-recovery-pg-data` 命名卷。 |

## 方案一致性与风险

文件级计划中的三个最小生产改点、RED 和轮换边界均实现；当前库只读、Host/worker/Provider 仍关闭。代次门避免普通原子替换与原位改写在同一 Host 进程内悄悄改变连接身份；拥有文件系统管理员权限并可伪造元数据的 actor 不在本门内。正式当前凭据、精确 assignment/Owner、八配置候选、批准/预算、自然首链仍待证，不能因测试 GREEN 判业务通过。独立 Host CLI `scripts/a0v_ecommerce_runtime_host.py` 的 `EXPECTED_ROLES` 仍写死 2026-09-12 历史角色名；在正式当前身份供给后须先做 E17-t 最小合同修正，绝不用旧角色冒充当前。浏览器指定 `browser-pilot` 未恢复，无新截图。
