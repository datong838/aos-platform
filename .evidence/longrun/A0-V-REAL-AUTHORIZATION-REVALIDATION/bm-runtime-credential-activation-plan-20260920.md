# BM 运行时凭据恢复与直系后继激活方案（2026-09-20）

## 1. 父权威与当前材料

- HEAD `19fc3595`；BL installation `ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc` / generation `116d12fc-93bc-4071-a973-fdc6830ea8b1` 已 exact detached：Binding rev8/epoch4 disabled/fenced/unknown、三资源 released、九路 legacy rev164/group191、definition rev118 disabled。
- BM registry recovery 已正式完成；新 trust root `a0v-local-ecommerce-recovery-v2` 与四个 published 坐标 `core@1.4.1 / niushop@1.23.1 / growth@1.10.1 / operations-base@1.2.1` 已逐项精确读回。
- 当前没有 BM installation；18181、Runtime Host、snapshot worker、cron 均为 0；商城源读取、Store Receipt、ecom_link、projection pending、canary 均保持 0。
- PostgreSQL 中既有三角色、host identity 与正租户 assignment 仍存在；仅原 `runtime-host-identities.json` 丢失。不得猜测旧密码，必须正式轮换。
- 上一波 `replacement-bm` 已含不可变 material-blocked 结果；本波使用独立 `replacement-bm-activation`，不得覆盖或删改旧证据。

## 2. 最小代码范围

1. `scripts/a0v_bm_runtime_credential_rotation.py`：为三个固定既有 login role 生成全新仓库外 `0600` credential file；先备份数据库，再在一个事务中轮换三个密码；提交后用三份 DSN 分别实际连接并验证角色/最小 membership、host identity、assignment 与零 canary。
2. `scripts/a0v_canonical_ecommerce_first_install.py`：仅为 `create_approved_first_installation` 增加向后兼容的 `operations_version="1.2.0"` 参数，替换函数内部两处硬编码；所有既有调用行为不变。
3. `scripts/a0v_bm_replacement_recovery.py`：切换到本波新 signed root / trust state / 四坐标 / 新 credential file，并锁定 exact BL predecessor；create 使用 `operations_version=1.2.1`。
4. 对应专项测试固定：凭据结果不可覆盖、三角色精确、四坐标、新材料路径、operations 参数与禁止 `run_definition`。

## 3. 串行 1–6 步

1. **只读 preflight**：回读 BL exact detach、四新版本 published、新 trust root/签名包、角色/host identity/assignment、Runtime Host=0、18181=0、attempt running=0、canary=0。
2. **凭据轮换**：写 credential intent 和私密文件、完成 DB 备份、单事务 `ALTER ROLE ... PASSWORD`，随后三平面逐一真实连接；未知结果只按新凭据能否全部连接进行对账，不创建 BM。
3. **兼容性实现与测试**：参数化 operations version，接线 BM wrapper；专项单测与既有 canonical installer 测试通过，方案/实现一致。
4. **create + lifecycle**：Runtime Host=0 条件下由 exact BL replacement ref 创建全新 BM；随后只启动一个正式 Runtime Host，读回第二 Host=0，串行 prepare → verify → stage → configure → enable。任一 operation 未正式 succeeded 或读回不一致立即停止。
5. **register/cutover/health**：enable正式 succeeded且 Binding rev4/epoch3 ready/enabled/unfenced、三资源 live后，才 register并 approve/prepare/pause/commit/validate/resume；目标九路 extension rev165/group192，definition保持 rev118 disabled；至少 12 次新增健康续租。
6. **封板**：独立读回 installation、binding、routes、definition、process/port、attempt=0 与业务零副作用；落 verification、精确提交。下一波自动进入 BM saved-snapshot recovery，并先走纯 HTTP 18181、Cron=false、snapshot worker=false、第二 Runtime Host=0 的读回门。

## 4. 停止条件

- 三角色中出现非 login/superuser/bypassrls/membership 漂移，host identity/assignment不精确，或 canary 非 0；
- 新凭据无法全部真实连接，数据库备份失败，或密码事务结果未知且无法只读对账；
- registry snapshot不能在新 trust root下精确解析四坐标，或 create/lifecycle/cutover任一步出现 unknown、stale、部分提交；
- 出现第二 Runtime Host、Cron、snapshot worker、手工 `run_definition`、商城源读取或 `dev-org` 写入。

上述任一条件只冻结并记录，不重发未知 operation。全程不 push、不动其他分支，230 L0 继续挂起。
