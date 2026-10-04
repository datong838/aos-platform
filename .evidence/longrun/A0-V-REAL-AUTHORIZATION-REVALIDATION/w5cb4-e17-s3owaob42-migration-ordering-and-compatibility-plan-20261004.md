# E17-s3o-w-ao-b42｜受限安装锁迁移与 Capability 发行迁移排程方案

## 上位合同及已证输入

- 231-3/4 与 BIND-1 要求安装头和 Registry 当前证据持有到最终提交，发行 Binding CAS 与 Receipt 必须同事务、专用非 owner 身份；当前真实库只读 `a0v_135`，Host/worker/Provider关。b41 只在 disposable PG 证明精确 `SECURITY DEFINER` 安装锁函数可行，正式角色/函数/Binding active 仍不存在。
- b25 原正式 Capability Receipt 方案已将下一 Alembic 头预计为 `a0v_136`，但因普通 runtime 可伪造 `evaluate` 的同事务行形状，明确**不新增**该迁移，待不可伪造 operation 证据。不能再独立抢用 `a0v_136` 给安装锁函数，形成两个同号迁移或跳过发行合同。
- `scripts/a0v_current_preview_http.py:_require_current_schema` 要求代码唯一头与库 `alembic_version` 精确相等。若先将任何 136 迁移提交 m1 而当前权威库仍135，最新代码/原卷完整启动验收的签名预检将以 `PREVIEW_CODE_SCHEMA_DRIFT` 禁入。每日重启硬门不能靠跳过预检或旧代码规避。

## 文件级执行

1. 只读复核 `a0v_135_extension_schema_acl.py`、b25 方案/全恢复合同、b41 函数试验、当前独立备份 SHA、当前代码头与正式角色状态；证据中分别列“已在克隆证明”“待冻结协议”“需要用户/外部合法来源”的边界。
2. 给正式迁移排程确定条件：先在隔离库关闭 b25 operation/Receipt 伪造反例并冻结写形状，再决定将受限安装锁函数与 Capability issuer ACL/Receipt guard 合并进入单一 `a0v_136`，或先做独立 `136` 并把后项顺延 `137`。选择需同时满足唯一 head、现有数据兼容、默认 PUBLIC EXECUTE撤销、正式 role/owner 与可撤回的调用协议；不得仅为刷新 head 发迁移。
3. 方案/代码复审后本波只出兼容性和顺序审计，不新增迁移/当前库写。下一独立安全波先做 b25 不可伪造 operation 证据 RED，之后按备份→全恢复克隆→零执行窗口→代码/库同步切换执行正式迁移；另行跑最新栈浏览器验收。当前实例缺正式 OIDC/issuer/active 安装只局部禁入。

## 不变边界

- 正向 org-org/dev-project，dev-org 零副作用；不读商城源、不回放旧12 Run、不手工 run_definition、不碰230 L0、不 push。Goal active；每日提醒每次到达仍独立以最新 m1 与当前权威卷完整重启，不能把本审计当作重启。
