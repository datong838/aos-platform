# W5CB4 E17-z 当前权威卷 a0v_110 安全迁移与最新栈验收

## 方案、源身份与备份

- 承接 `m1@4ba2d80c`、`AOS-000840` 和本波文件级方案。`docker --context colima-aos-extension inspect aos-a0v-recovery-pg` 读回原命名卷 `aos-a0v-recovery-pg-data`；签名预检脚本在迁移前退出 0：`aos_current_preview_20260927@a0v_109`、唯一安装 approved、4 个签名包 published、运行绑定 0。
- 新独立归档 `/Users/ddt/work/projects/ai_agent/.aos-e17z-backup-20260928-CewNIz/aos_current_preview_20260927_a0v109.dump`，3,893,668 bytes、0600、SHA256 `fb188356f1fa7b2d3ecd22f90271bd6a2b8f5bcdf857c43d46aedb50844b8ccc`；`pg_restore --list` 退出 0、目录 5509 行。原备份及卷均保留。
- `pg_restore --exit-on-error` 到新库 `aos_e17z_restorecheck_20260928` 退出 0；源/克隆均 `a0v_109`、571 张原 public 表逐表行数摘要 `c40d76e36ec3e41344716782b980e1e6f853a0f3e4fa1c775b133f3bfea36bb5`，安装 1、包版本 4、绑定 0、预算修订 0。克隆单步 `a0v_109→110` 退出 0，四张新表 0、RLS FORCE 与 `aos_runtime` SELECT/INSERT-only 均通过；原表行数不变。此为同集群独立库恢复演练，不能声称异机灾备。

## 零执行窗口与重启

- 发现 `scripts/a0v_current_preview_http.py` 固定 `a0v_109`；先改测试 RED（1 failed/2 passed，退出 1），只改脚本常量为 `a0v_110` 后 3 passed、退出 0。
- `launchctl bootout` 停 Web、TERM 旧 API，8080/8434/18181 均无监听；当前库非空闲连接 0，备份 SHA256 再核对，容器挂载原卷。源库单步 Alembic `a0v_109→a0v_110` 退出 0，没有修改旧业务行。
- 重启原 PG 容器后首次 `pg_isready` 暂无响应（退出 2），第二次接受连接（退出 0）；签名预检读回 `a0v_110`、安装 approved、4 published、binding0。启动最新 m1 API（migration disabled、Runtime Host 0、workers 0），重载 8434 launchd Web。8080 `/v1/health` 和 `/v1/ready`、8434 `/aip/skill-publish` 与 `/apollo/assets` 均 HTTP 200，18181 无监听；PG 仍挂原卷。
- 只读回查当前库：原 571 表行数摘要迁移前后一致；新四表全 0；预算 Head/Revision 0、唯一安装 1、签名包 4、绑定 0；`org-org/dev-project` 当前正式成员仍只有 `owner:1`。公开 active 入口测试仍为 422，Host 禁入。

## 回归与边界

- `AOS_DOTENV_DISABLED=1 ... pytest -q` 覆盖预览脚本、E17-y2 PG/合同/API/预算邻接：38 passed、退出 0；`compileall -q`、`git diff --check` 退出 0。
- 8434 的 `/workbenches`、`/ecommerce`、`/aip/skill-publish` 路径 HTTP 200 只是 SPA 可访问；当前无八工作台业务入口，不能算八页交互验收。browser-pilot 工具本波不可用，未制作截图或伪称浏览器通过。未读商城源、未重放旧 12 Run、未手工 Run、未写 `dev-org`、未启 Host/Provider。
- 下一波继续当前正式第二审批主体、费用上界与批准原子消费；配置八候选/Host Owner/自然首链仍为阻断，不因迁移重启变 GREEN。
