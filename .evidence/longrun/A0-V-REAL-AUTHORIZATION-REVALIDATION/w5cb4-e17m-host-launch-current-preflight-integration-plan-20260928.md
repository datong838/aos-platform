# W5CB4 E17-m｜当前签名只读预检接入 Host 启动入口方案

## 上位复习与风险

231-2 要求签名制品和隔离 Host，231-3 要求安装/绑定/配置/权限/预算和操作 Owner 分离。E17-l 的只读脚本只证当前签名库、三身份、Host identity/assignment 与八项**候选**；它不证配置实际绑定、预算审批、生命周期 Owner。现有 `a0v_ecommerce_runtime_host.py` 虽已要求显式凭据，仍可显式传旧库身份并只对三身份彼此同库进行检查，且未消费 E17-l 预检。当前真实库 Host 仍禁止启动。

## 文件级施工

1. 修改 `scripts/a0v_ecommerce_runtime_host.py` 的命令入口：增加显式 `--signed-receipt`，在任何 `_configure_environment`、`_build_runtime`、worker 构造之前调用 E17-l 只读预检；缺 Receipt 或预检失败以固定码写 SAFE_BLOCKED，保留原锁和状态文件语义，不泄露密钥。
2. **即使预检 GREEN，也不自动转为 Host 启动授权。** 当前缺正式安装生命周期 Owner 与已批准、精确绑定的四源配置/预算。入口在本波固定返回 `FORMAL_OWNER_AUTHORITY_UNPROVEN`；下一独立波需依据 231-3 的正式 Receipt/Owner 合同替换这个硬门，并做完整真实准入验收，不能以字符串参数或测试值绕过。
3. 修改 `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py`：先 RED 验缺 Receipt、旧库/签名预检拒绝在 `_serve` 前生效、预检 GREEN 仍不能启 Host；保留原 `_serve` 内部逻辑测试，但不能把内部替身视为命令入口授权。最小实现后跑专项与相邻累计、当前无凭据现场失败封闭；不启动 Host 或写当前库。
4. verification、D-waves/01/06/Prime、m1 精确提交，不 push。

## 下一门

正式 Owner/审批/绑定来源必须被受信 DB Receipt 读取并与当前安装和 TenantScope 精确绑定；在此之前保留硬禁入。八候选数大于零不足以授权。浏览器 `browser-pilot` 当前不可用，截图仍待补。
