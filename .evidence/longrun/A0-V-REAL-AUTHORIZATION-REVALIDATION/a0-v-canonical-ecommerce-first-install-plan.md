# A0-V Canonical 电商包首装与运行就绪方案

## 1. 现场结论

`aos-a0v-recovery-pg/aos_meta_head` 是 2026-08-05 备份迁移到当前 Alembic head 的隔离恢复库。2026-09-10 的只读事务确认：目标四个 Registry bundle/version 为 0，`org-org/dev-project` 的 composition、installation、runtime operation、runtime binding 均为 0。

因此当前是无 baseline 的 canonical 首装，不是 successor 升级。`workshop_w1_10_successor_install.py` 要求一个已有 effective active installation，并且固定历史 1.0/1.1/1.3 版本；继续复用会以 `EFFECTIVE_INSTALLATION_AMBIGUOUS` 或 release drift 阻断，不能改库伪造 baseline。

输入制品固定为 `A0V_RUNNABLE_ECOMMERCE_CANDIDATE_QUALIFICATION_GREEN` 的同一份 staging tree：

- 源提交：`ae395e4bbdf898b703edf26fe4876d13f6cdc5a4`
- staging tree：`sha256:dedfae13faa85c7a506f834aed50afb6d502b952df73796766df1fa37cd1f49e`
- build receipt：`sha256:894e9812c21a9fae455419b3219c8e30a85f957bc1a63450ef6655d34d717333`
- 版本：core 1.1.0、niushop 1.1.0、growth 1.4.0、operations-base 1.2.0

## 2. 施工范围

新增 `scripts/a0v_canonical_ecommerce_first_install.py`，默认只做 preflight，显式 `--apply` 才允许连接指定隔离数据库。脚本按以下阶段串行执行：

1. **输入与目标预检**：核对 git HEAD、build/qualification receipt、staging tree、四包 content hash、三 OCI identity、Docker 隔离条件、目标数据库名 `aos_meta_head`、Alembic head、目标租户和零/可重放基线。数据库不是显式隔离名称、存在未知 active 安装、摘要漂移或 Docker cache 缺失时失败关闭。
2. **本地开发签名根**：私钥只创建于仓库外恢复目录，模式固定 0600；公钥 trust-root JSON 单独落在恢复目录。日志和证据只记录 key id、public revision、有效期和文件模式，不记录私钥或公钥正文。签名发生在 staging 的临时副本，原始 staging 保持 unsigned。
3. **Canonical Registry**：使用 RegistryService 创建缺失的四个 bundle，并以分离的 creator、validator、publisher actor 依次 create version、validate、publish。每个既有对象必须 exact readback；同版本任一 manifest/artifact/content/signature/evidence 漂移均阻断，不覆盖不可变记录。
4. **无 baseline Composition**：读取当前 RegistrySnapshot，请求 niushop 1.1.0、growth 1.4.0、operations-base 1.2.0，由 resolver 唯一加入 core 1.1.0；持久化 exact lock，校验四节点、三依赖、八模块贡献与同一 content hash。
5. **Installation 职责分离**：maker 创建和 submit，checker 使用 lock、permission、migration、contribution 四个 exact hash approve。runtime bundle 禁止走 legacy apply/verify；安装保持 approved 直到 runtime preparation 成功。
6. **三 runtime 实体生命周期**：使用当前 RuntimeLifecycleService/PreparationWorker、`colima-aos-extension` 和已缓存 exact OCI；按一个 installation generation 计划三 member，完成 runtime-apply 与 runtime-verify。必须校验隔离容器配置、registration 1/2/9 共 12 operation、schema condition、资源租约释放、binding 三行 ready 且默认 `enabled=false + operation_fence=true`。
7. **配置与启用**：只消费当前 A0-V 已存在且 exact 的本地配置权威；缺少 runtime policy/profile/config、权限或 generation target 时保留 actionable blocker，不伪造配置。满足后以 maker/checker 边界完成 configure/enable，使三行同 generation、`enabled=true`、`operation_fence=false`，并生成正向租户的八模块投影。
8. **回读与反证**：GET/只读事务验证唯一 active installation、四个 exact resolved bundle、三 runtime ready binding、八个 available module；`dev-org/dev-project` exact installation/runtime/module 查询必须 404/空。只验证 registration 和读模型，不派发九条业务命令。

## 3. 幂等、恢复与停止规则

- 每个 Registry/Composition/Installation/runtime command 使用固定阶段前缀与 exact 输入 hash 派生的幂等键。重跑只能返回同一对象/Receipt；不得新建第二 active leaf 或第二 generation。
- 任何 unknown outcome 先按 command receipt、operation journal、resource lease 和 exact target 回读对账；不得重发。
- apply 前创建 `aos_meta_head` 的新逻辑备份并记录 SHA-256。失败时保留已成功的 canonical 阶段和 receipt，以状态机续跑；不直接删除审计数据。
- 不自动 rollback 已发布不可变版本。安装在 active 前失败则保持其真实状态；runtime partial 必须先 fence，再按既有 reconciliation/cleanup 合同处理。
- 同一阶段两次出现无法解释的摘要/状态漂移，或将触发 Provider、外部业务写入、数据出境、费用、共享/生产迁移、230 L0 时立即停止该动作并落 blocker。

## 4. 安全边界

- 目标只允许隔离恢复库 `aos_meta_head`，不允许 `aos_meta`、共享开发库或生产库。
- 不调用真实 Provider，不执行栖月汇经营写入，不调价、退款、发货、发送或外部发布。
- `org-org/dev-project` 只承载本地隔离安装证据；`dev-org/dev-project` 只作负向 canary。
- 签名私钥、数据库口令、token 和 Secret 正文不得进入 stdout、Git、receipt 或证据文档。
- Prime/OAuth 与本施工无关，不作为运行时依赖或信任根。

## 5. 验证矩阵

1. preflight 不连接数据库写事务、不创建密钥、不调用 Docker create/start。
2. 错误数据库名、错误 HEAD、错误 receipt/tree/content/image digest、已有未知 active、跨租户、actor 未分离全部失败关闭。
3. Registry 四包首次发布与重放 exact；历史不可变 release 专项继续通过。
4. Composition 首装 exact 四节点/三边；重复解析得到同一 payload/hash 语义。
5. Installation maker 自批拒绝、checker 精确批准、stale ETag/摘要拒绝。
6. 三 OCI 真实 registration 与 runtime apply/verify；任一 member 失败不得产生 active partial。
7. 配置缺口产生精确 blocker；配置存在时三 binding 同 generation 并启用。
8. 正向唯一 active/三 ready/八 module，负向 404/空；最终重跑不新增资源。
9. 运行受影响的 Registry、Composition、Installation、extension runtime、Workshop catalog 专项与 A0-V collector/validator。

## 6. 退出条件

只有以下条件同时满足，才能写 `A0V_CANONICAL_ECOMMERCE_FIRST_INSTALL_RUNTIME_READY_GREEN`：

- 四个 exact 版本 canonical PUBLISHED；
- 一个无 baseline composition lock 与一个唯一 active installation；
- 三个 runtime member 通过实际 OCI admission、registration、apply、verify、configure、enable；
- 八模块在正向租户全部 available，负向租户不可见；
- 首次和重放 receipt、备份、摘要、测试和零 Provider/零外部业务效果证据齐全。

该标记仍不等于 A0-V 总体 GREEN；SourceReadiness、模型/Provider 健康、预算、批准、StageTemplate、ResponsibilityPlan 等其余门必须由 A0-V 采集器重新确认。若配置权威缺失，本切片以 `...INSTALL_ACTIVE_CONFIGURATION_BLOCKED` 结束并把具体恢复入口交回 A0-V，不以伪造配置越过。
