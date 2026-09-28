# W5CB4 E17-i｜当前 Host 签名、三身份、OCI 与 Owner 只读矩阵（2026-09-28）

## 方法

先读 242/243 与 `runtime_identity.py` 的三连接平面条件，再对当前卷执行签名预检和 PostgreSQL 只读事务。`.env` 只打印指定键是否配置及签名目录是否存在，不输出 DSN/密码。没有启动 Host/worker/Provider、没有写库。

## 当前矩阵

| 必要条件 | 新鲜证据 | 判定 |
| --- | --- | --- |
| 当前签名 bundle | `a0v_current_preview_http.py --signed-receipt ...` 退出 0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：当前库 `aos_current_preview_20260927@a0v_109`、唯一 approved 安装、4 published、签名树 hash/Registry 摘要一致、binding 0。`.env` 的 `AOS_BUNDLE_ROOT` 已配置且目录存在。 | 控制面签名源可核验；不等于 Host 加载。 |
| 三个数据库角色 | 当前库只读 `pg_roles`：`aos_a0v_web_20260912`、`aos_a0v_runtime_20260912`、`aos_a0v_directory_20260912` 均可登录、非 superuser、非 BYPASSRLS；runtime 仅 runtime 组，directory 仅 directory 组，web 均非成员。 | 数据库角色结构存在；不能证明当前受保护凭据能分别连接该库。 |
| 当前三身份引用 | `.env` 中 `AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE`、`AOS_EXTENSION_RUNTIME_DATABASE_URL`、`AOS_EXTENSION_DIRECTORY_DATABASE_URL` 均未配置。243 已证明历史三身份文件分别落旧 `aos_meta_head`。 | 当前正式三身份不齐；预览 API 特权连接不能代替 Web 正式身份。 |
| OCI | `docker context ls` 包含 `colima-aos-extension`，但 `.env` 的 `AOS_EXTENSION_OCI_CONTEXT` 未配置；当前 CLI 默认 context 为 test-only。 | context 可用不等于 Host 有固定受信 OCI 来源。 |
| Host assignment/identity | 当前库只读 `org-org/dev-project`：`extension_runtime_host_assignment=0`；全库 `extension_runtime_host_identity WHERE enabled=true` 为 0。 | 无精确当前 Host Owner/assignment，禁止启动。 |
| 安装与运行 | 当前安装 ID `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`，revision 3 approved、activeRevision=NULL、createdBy/requestedBy=`a0v-current-preview-install-maker`，有 decision 记录；operation/binding 均 0。8080 健康 200，18181 无监听。 | 安装审批存在，但制作者是预览流程标识，不能充当正式运行 Owner；无运行资源。 |

## 后续

当前签名源仍有效，四项执行关键条件（当前三身份引用、受信 OCI 固定配置、启用的 Host identity/精确 assignment、正式配置/批准）未齐。不能以旧库凭据、预览超级账号或页面可达补齐；Host/worker/Provider 保持禁入。下一波可独立做正式三身份和 Host assignment 的产品/运维配置合同与只读验证器，必须要求受保护来源、同库、互异、非特权和精确租户 Owner；实际凭据写入需由受权 Owner 通过受保护路径完成。浏览器 `browser-pilot` 截图与首链仍未验收。
