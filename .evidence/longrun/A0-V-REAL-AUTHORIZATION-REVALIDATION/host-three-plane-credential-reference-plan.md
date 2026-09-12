# 独立 Host 三身份文件引用

2026-09-12，ead2e83f，m1 串行。目标为已授权原 Host 恢复前置，不改租约 TTL、安装状态、控制权限或真实源。

具体修改：services/aos-api/aos_api/extension_runtime/runtime_connections.py 将既有受保护读取复用于三身份；返回按 plane 索引的内存 DSN，要求三个角色和 DSN 分别互异。文件仍绝对路径、最终节点非符号链接、当前用户、0600、普通文件、大小限制；坏引用不回退旧环境。runtime/directory/web 三连接仍遵守各自 IDLE、directory readonly/repeatable-read、后续数据库实际身份门；无引用才兼容旧配置。

services/aos-api/aos_api/asset_registry/control_wiring.py 允许已配置文件引用进入原依赖构造，再由原 selector 实际探测三身份，不把路径存在当授权。disabled/缺 platform 仍不访问数据库。scripts/a0v_ecommerce_runtime_host.py 仅设置非密钥文件路径及原非秘密启动配置，删除继承的三份 DSN 环境，不写明文环境。现有精确角色文件检查保留，不能先 resolve 掉符号链接再检查。

测试为 tests/extension_runtime/test_runtime_connections.py、test_production_runtime.py、test_a0v_ecommerce_runtime_host.py。先证明 directory/web 未消费引用及启动入口泄漏环境的失败，再补实现。覆盖三身份精确连接、只读、坏引用/角色混用/DSN混用时全体拒绝且无fallback、路径模式依赖构造、旧无文件路径兼容、serve不绕过symlink检查。合成凭据不得复制真实值。

实现通过后启动原签名根的独立 Host 新状态文件，先确认唯一进程，再回读恢复/禁入状态。已释放原代际不可复活；若缺正式恢复入口，继续按方案补齐正常控制路径，不直接改数据库。API 保持旧进程，主库不迁移。230 L0 挂起，不 push。
