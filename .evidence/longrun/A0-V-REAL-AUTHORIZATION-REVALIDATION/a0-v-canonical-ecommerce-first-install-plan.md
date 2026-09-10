# A0-V Canonical 电商包首装与运行就绪方案

## 1. 现场结论

`aos-a0v-recovery-pg/aos_meta_head` 是 2026-08-05 备份迁移到当前 Alembic head 的隔离恢复库。2026-09-10 的只读事务确认：目标四个 Registry bundle/version 为 0，`org-org/dev-project` 的 composition、installation、runtime operation、runtime binding 均为 0。

因此当前是无 baseline 的 canonical 首装，不是 successor 升级。`workshop_w1_10_successor_install.py` 要求一个已有 effective active installation，并且固定历史 1.0/1.1/1.3 版本；继续复用会以 `EFFECTIVE_INSTALLATION_AMBIGUOUS` 或 release drift 阻断，不能改库伪造 baseline。

输入制品固定为结构兼容修正后的 `A0V_RUNTIME_SCHEMA_COMPATIBILITY_QUALIFICATION_GREEN` v4 staging tree：

- 源提交：`4f9eee9f4480a2b589409116eda221fe618bbbe9`
- staging tree：`sha256:26a5942e8087252df8f72e5430e4c4c6e42c906a8f814fe2df428d33c1293950`
- build receipt：`sha256:b473385f353d28dfe5cd6a04cf4c8610c7b77496c7558e4f429271fa8a510638`
- qualification receipt：`sha256:e8574f6b3bf2d7eb4d22bf811dc06174ffce18fe8f7f091a0bbebfd93f592da0`
- 版本：core 1.1.0、niushop 1.1.0、growth 1.4.0、operations-base 1.2.0

## 2. 施工范围

### 2.1 runtime verify 前置修正

首装路径复核发现，三个已资格化 runtime Candidate 均缺少 `artifacts/schema-requirements.json`。当前 `CurrentSchemaConditions` 对带 `exports.schemas` 的 runtime 明确禁止空要求；因此 v3 只能证明 OCI admission，不能证明 runtime verify。

在编写首装执行器前，先为三个 runtime Candidate 各增加签名内的：

- `artifacts/schema-compatibility.json`：固定 `alembicRevision=a0v_001`、该包依赖的现有平台 relation 清单和 `noPackageOwnedMigration=true`；它声明包只通过 host ports 使用已经由 AOS Alembic 管理的平台 schema，不创建包私有表。
- `artifacts/schema-requirements.json`：唯一 requirement 的 version 固定为 `aos-platform-a0v-001`，`migrationHash` 精确等于上述 compatibility artifact 的 SHA-256。

首装维护步骤只在目标库确认为 `aos_meta_head`、Alembic revision 为 `a0v_001` 且全部 relation 存在后，使用 `SchemaRequirement + apply_once` 登记“已安装平台兼容性”Receipt；callback 只执行只读断言，不运行 DDL。该 Receipt 不是伪造迁移成功：其签名 artifact、实际数据库 revision 和 relation 集必须三者一致，任何缺项都阻断。

完成修正后重新生成 v4 build/qualification receipt；v3 保留为前一时点 OCI 资格证据，但不得作为首装最终输入。

### 2.2 首装执行器

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

- 数据库容器固定为隔离 context `colima-aos-extension` 中的 `aos-a0v-recovery-pg`，数据库固定为 `aos_meta_head`。执行器必须同时核对 Docker 容器名和 SQL `current_database()`；不接受仅靠连接串名称推断。
- 每次首次 mutation 前，以容器内 `pg_dump --format=custom` 生成仓库外备份到 `.aos-recovery-20260910/backups`。回执只记录路径、字节数和 SHA-256，不记录连接参数或口令；备份失败或空文件时禁止继续。
- canonical 本地开发签名根固定落在 `.aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install/signing`。目录模式 0700、私钥模式 0600；重跑必须读取同一 Ed25519 key 并得到同一 trust-root revision，不允许静默轮换。
- 签名后的完整 bundle tree 固定落在上述 state 目录，先写临时目录并完成 ReleasePolicy 回读，再原子替换；源码 Candidate 与 v4 staging 始终保持无签名。
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

### 5.1 多成员签名 artifact 路由补强

运行时开工复核确认，`PreparationWorker` 的 `load_record` 已按 `member.selected` 取包，但 `open_signed_session` 收到的是一个无成员上下文的二参数 `read_artifact(path, limit)`。单包测试成立，多个包含有同名 `artifacts/backend-runtime.json`、`artifacts/schema-requirements.json` 时无法证明读取的是当前 member 的签名字节。

在实际三包 apply 前，给 `PreparationWorker` 增加可选的 `read_member_artifact(selected, path, limit)` 宿主注入；worker 必须在 member factory 内绑定 `member.selected` 后才把二参数闭包交给 admission。旧 `read_artifact(path, limit)` 保持兼容，现有单包调用不变。专项测试至少证明两个 member 的同名路径分别读到自己的字节，且未提供新入口时仍使用旧 reader。A0-V 首装执行器必须使用成员感知入口，不得靠全局当前包、遍历顺序或同名文件恰好一致。

## 6. 退出条件

只有以下条件同时满足，才能写 `A0V_CANONICAL_ECOMMERCE_FIRST_INSTALL_RUNTIME_READY_GREEN`：

- 四个 exact 版本 canonical PUBLISHED；
- 一个无 baseline composition lock 与一个唯一 active installation；
- 三个 runtime member 通过实际 OCI admission、registration、apply、verify、configure、enable；
- 八模块在正向租户全部 available，负向租户不可见；
- 首次和重放 receipt、备份、摘要、测试和零 Provider/零外部业务效果证据齐全。

该标记仍不等于 A0-V 总体 GREEN；SourceReadiness、模型/Provider 健康、预算、批准、StageTemplate、ResponsibilityPlan 等其余门必须由 A0-V 采集器重新确认。若配置权威缺失，本切片以 `...INSTALL_ACTIVE_CONFIGURATION_BLOCKED` 结束并把具体恢复入口交回 A0-V，不以伪造配置越过。
