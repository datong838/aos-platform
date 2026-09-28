# W5CB4 E17-j｜Runtime Host 必须显式选择正式身份文件（2026-09-28）

## 上位与风险

- 231-2/231-3 的隔离运行与三身份要求当前受保护来源、Web/Runtime/Directory 同库互异非特权，精确 Host assignment/Owner；E17-i 证明当前三身份引用缺失，历史身份文件落旧 `aos_meta_head`，Host 必须禁入。
- `scripts/a0v_ecommerce_runtime_host.py` 的 CLI 目前 `--credential-file` 默认指向 `.aos-recovery-20260912/.../runtime-host-identities.json`。即便后续组合根可能因当前安装/权限拒绝，CLI 自动选历史文件违背 E17 “不得用旧目录”的显式准入边界，且可能误连旧库。

## 文件级最小改动

1. `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py`：先加 RED，未显式传 `--credential-file` 时，即使 bundle/trust 参数存在也应 `SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`，`_serve` 不被调用；显式路径仍走原 0600/三角色校验。已有 mock `_serve` 的成功/异常测试补显式 dummy 参数，竞争锁和非法 interval 原先的优先阻断保持。
2. `scripts/a0v_ecommerce_runtime_host.py`：移除历史身份文件默认值，解析结果缺路径时在锁/interval 后、`_serve` 前写安全状态并退出 2。不得读取 `.env`、自行扫描历史目录、创建凭据或启动 Host；现有签名根、OCI、三身份预检逻辑保持。
3. 同目录 verification：RED/专项/相关累计、方案/代码和风险复核；不实际启动 Host，不写当前库。m1 精确提交后更新 D-waves 与上下文。

该切片仅消除历史默认凭据；当前正式凭据、OCI、Host assignment/Owner 仍缺，不能因此启 Host。
