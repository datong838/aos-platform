# BN canonical alias 修复、失败 BM 退休与直系后继方案（2026-09-20）

## 1. 当前权威

- HEAD `176d04b7`。BM installation `370d4287-3402-40bb-b3da-d479633da7c4` 为 approved rev3、无 binding；唯一 runtime-apply `391bc3e3-ccc9-40c4-9f08-3f36686d882d` 已正式 failed，三资源 released。
- 确定性根因是 `.1` 版本 artifact refs 使用 `bundle://a0v-bm-recovery/...`，生产 runtime loader只 allowlist `server` 与历史正式契约 `a0v-canonical`；禁止扩大 allowlist掩盖错误。
- 新信任根、私钥与三角色新凭据均有效；本波复用，不再次轮换。

## 2. 串行步骤

1. **plan/preflight**：固定 BM approved/failed/no-binding/released 边界、`.1` registry 状态、新 trust/credential、Host=0、18181=0、attempt=0、canary=0。
2. **canonical alias rebuild**：以已 qualification 的仓库外 `.1` unsigned candidates 为输入生成 `.2` 四坐标；复用隔离 builder 完成 build/qualification；签名仍使用 `a0v-local-ecommerce-recovery-v2`，发布 source/artifact refs 必须为 `bundle://a0v-canonical/...`。
3. **production artifact proof**：使用与生产 control wiring相同的 `ManifestLoader({"a0v-canonical": signed_root})` 和新 trust root，逐个从 registry artifact source ref读取 runtime image index并校验 digest；旧 `.1` 不覆盖、不删除。
4. **退休 BM**：复用 approved-never-active正式 uninstall service；要求 BM 无 binding、所有 operation terminal、资源 released、attempt=0、业务零副作用。一次 uninstall加同 key replay读回 `uninstalled`；不调用 disable、不伪造 detach receipt。
5. **创建与激活 BN**：以 BM exact uninstalled replacement ref创建 BN；Runtime Host=0起步，只启动一个 Host，第二 Host=0；串行 prepare/verify/stage/configure/enable，随后 register/cutover至九路 extension rev165/group192，definition rev118保持 disabled，并记录至少12次健康续租。
6. **verification/commit**：独立读回版本、artifact、installation、binding、route、definition、process/port、attempt=0与业务零副作用；落盘 verification并精确提交。下一波进入 BN saved-snapshot recovery。

## 3. 停止条件

- `.2` 任一 source/artifact ref不是 `a0v-canonical`，production loader读取失败，或 qualification非 GREEN；
- BM出现 binding、非终态 operation、未释放资源、attempt、业务写或canary；
- uninstall/create/lifecycle/cutover出现 unknown、stale或部分提交；
- 第二 Runtime Host、cron、snapshot worker、手工 `run_definition`、商城源读取或 `dev-org` 写入。

未知结果只读对账，不重发。全程不 push、不动其他分支，230 L0继续挂起。

## 4. 执行中边界补充（registration identity）

- 重启后的正式 successor preview 已通过，但首次 register 在事务建立前以
  `registration identity reference is invalid` fail-closed；外部状态中只有冻结的
  register intent，不存在 registration receipt，因此没有未知数据库提交边界。
- 只读检查确认历史 `.aos-recovery-20260913` 的受保护 registration identity 文件已
  不存在。不得回退到 runtime、maintainer、Web 或本地管理员身份。
- 在继续步骤 5 前，为现有 `aos_ecommerce_registration_control` 独立登录生成新的
  0600 identity 并轮换其密码。必须保持 `NOINHERIT`、无超级/绕过 RLS/建库/建角色/
  replication 权限，且可达角色精确为 `aos_runtime` 与
  `aos_extension_maintainer`、均无 admin option。连接验证成功后才能读取既有 intent
  并进行唯一一次正式 register；该恢复不得产生 installation、route、attempt、业务或
  canary 写入。
