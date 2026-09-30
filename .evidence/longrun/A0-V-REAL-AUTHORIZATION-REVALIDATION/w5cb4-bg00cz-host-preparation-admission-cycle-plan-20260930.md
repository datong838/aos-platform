# W5CB4 BG00cz｜当前 Host 准入顺序核验方案

## 上位及范围

- 231-3 的自然顺序是 `approved→runtime-apply→runtime-verify→active→configure→enable`；E16 的 HTTP `runtime-apply` 要求同一 API 进程内可执行 Host，不能以独立 CLI 状态冒充。
- E17 当前签名制品、三平面独立身份、精确 Host identity/assignment 与 OCI 必须真实核验。当前库只读，不补造身份/配置/Receipt，不启自然 worker 或 Provider。

## 文件级只读审计

1. 读 E16/E17/231-2/3/9、`runtime_directory.py`、`production_runtime.py`、`control_wiring.py`、`main.py` 与 `scripts/a0v_current_runtime_host_preflight.py`，画出 API 受理与 Host 启动依赖。
2. 对当前库只读计数 `extension_runtime_host_identity/assignment/operation/binding/configuration`，运行当前签名 Host 预检；无凭据时只记录固定 reasonCode，不尝试旧目录、旧角色或高权限账号。
3. 区分“231-3 本身无循环”与“当前 E17 签名路径的预检门形成顺序环”。只提出下一波最小施工边界，不在没有跨文件方案/RED 前改 Host 启动代码。

## 下一波文件级入口

- `scripts/a0v_current_runtime_host_preflight.py`、`asset_registry/control_wiring.py`、`main.py`、`extension_runtime/production_runtime.py` 及对应测试：设计显式的准备态 Host。必须仍经当前签名、物理库、三身份和精确 assignment；八候选不足时只准生命周期准备/验证，所有自然业务 worker/Provider 关闭。完整业务 Host 继续按原候选及配置/批准门。
- 先 RED 再最小实现；当前实例因正式凭据和 assignment 缺失继续拒绝，不用测试正向冒充真实启用。
