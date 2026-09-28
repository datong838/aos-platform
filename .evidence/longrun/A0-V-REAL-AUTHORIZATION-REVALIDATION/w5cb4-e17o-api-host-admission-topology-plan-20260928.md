# W5CB4 E17-o｜API 内嵌 Host 与独立 Host 准入拓扑审计方案

## 依据及范围

E17-n 证明进程内生命周期 Owner 在 pending 操作之后构造。继续按 231-3 调查 runtime-apply 的真正受理入口，不编码、不启 Host。E17-m 只加固独立脚本；不能假设 API 内嵌 Host 自动继承该门。

## 文件级只读检查

1. 对照 `routers/bundle_runtime_installations.py:current_preparation_executable`、`lifecycle_service.py:request_preparation`、`main.py` Host startup、`production_runtime.py` selector 和 `a0v_ecommerce_runtime_host.py` 独立脚本，绘出 API 操作受理到 Host 消费的精确先后和进程边界。
2. 检查 E17-l 的当前签名/三身份交叉预检是否被 API 内嵌 Host 启动路径调用；查 API 当前 flags 与健康，只读核 operation/outbox 仍零。任何无法证实的 Host 可执行性仍禁入。
3. 给出下一波最小代码边界：API 内嵌 Host 启动在 selector/worker 前必须走受信当前签名交叉预检，避免只修独立脚本留下可绕路径；如何测试缺 Receipt/旧库/未知结果与无副作用。正式配置/预算/审批和正向 Host 启动仍独立，不能假门冒充完整业务许可。
