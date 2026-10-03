# E17-s3o-w-ao-b4｜当前正式身份来源与切换门只读核验

## 来源与范围

按同前缀 plan 复习 231-4、AIP-7 22、BIND-1 31 与 D-wave；只读核 repo `.env` 的**变量名**、`aos-platform`/`aos-recovery` 内 `.pgpass` 的路径/权限元数据、源码、当前原命名卷只读 SQL、端口及两 PG 容器卷身份。未读取凭据正文或商城源；未对原库执行 DDL/DML。

| 核对项 | 可复核命令/结果 |
| --- | --- |
| 原卷与新克隆隔离 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg --format ...` → running、`aos-a0v-recovery-pg-data:18435`；test-only context 的 `aos-a0v-test-pg` → running、独立匿名卷 `3fa61191…735e0:5433`，两命令 exit0。 |
| 原库版本/角色/Host | `docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -X -qAt -v ON_ERROR_STOP=1 -U aos_app -d aos_current_preview_20260927 -c 'BEGIN READ ONLY; ... COMMIT;'` → `a0v_135`，`aos_aip_binding_readiness_reader`0、`aos_aip_capability_issuer`0、Host assignment0、Host identity0、active binding0、Installation1、RegistryReceipt6，exit0。`aos_aip_registry_issuer`也0，但它不是此 Capability 路径应有 issuer，已按源码区分。 |
| API 组合要求 | `services/aos-api/aos_api/routers/aip_bindings.py:build_capability_binding_service` 要求 Reader/issuer 两组完整 HOST/PORT/DATABASE/PASSFILE、同库不同凭据文件且不能同 inode；缺全部则默认无 readiness 服务。`aip_registry_issuer_connection.py` 精确 `capability_lifecycle` 需 `aos_aip_capability_issuer`。源码只读核验 exit0。 |
| 本仓库 env/候选文件 | 对仓库 `.env` 仅解析 key 名：正式 `AOS_AIP_BINDING_*`0、`AOS_OIDC_*`0，exit0。仅在 `aos-platform`/`aos-recovery` 搜 `.pgpass` 元数据，发现 `aos-recovery/.aos-testonly-bg00cf-3r_lw6yp/api.pgpass` 和 `.aos-bg00cm-issuer-qTLrIa/issuer.pgpass` 两个0600文件；前者目录明确 test-only，后者是历史隔离 issuer 现场，均未见当前正式来源证明，未读取内容、未接 API。搜索范围之外不能据此断言文件不存在。 |
| API/Web/Host 窗口 | `lsof -nP -iTCP:8080 -iTCP:8434 -iTCP:18181 -iTCP:18435 -sTCP:LISTEN`：8080 PID51474、8434 PID51498、18435 ssh；18181 无监听。命令因18181缺项退出1，该缺项是预期关态，但 API/Web 当前运行，**零执行窗口未取得**。 |
| 正式 API/Host 前置 | `scripts/a0v_current_preview_http.py` 受限 API 要外部 HTTPS OIDC JWKS/issuer/audience及独立受限 API login；`scripts/a0v_current_runtime_host_preflight.py` 要私有三平面 credential_file、精确 Host assignment/identity 与候选配置。现有当前库 Host 0/0，不能启 Host。 |

## 判定与后续

- 当前库 Reader/issuer 写入门 **未通过**：没有可验证的正式私有凭据来源和独立正式角色，API/Web 零执行窗口也未取得。b3 新鲜克隆全备/事务成功只证明隔离恢复链；切前仍需新的当前一致全备/独立完整恢复，不能复用 test-only 凭据或 b3 备份替代切前状态。原库继续只读，Host/worker/Provider关，首链 pending。
- 下一安全候选按 D-wave：①正式 Provider OIDC/Owner/secretRef/健康容量来源，当前实例缺外部 OIDC，先只读核原合同与来源；②ToolBinding issuer/RegistryReceipt 的当前签名 ToolDefinition 来源，先只读核已签 bundle 清单和发行链。两者均不需要先写当前库，可分别推进；正式受限 API/Host 实例操作继续禁入。
- 本波只读、无生产代码/API/Web/页面改动，浏览器不适用；文件级方案和现场核对一致。仓外未被本次搜索覆盖的正式凭据可能存在，不能写成全局不存在；若后续找到，先精确身份与权限预检，不直接切换。
