# 1.6 重新首次安装与宿主验证

2026-09-12。前置：旧 1.4 实例 uninstalled@4；新三坐标已签名 published，真实 Session qualification green。

复用正式首装服务，给执行器增加显式版本和幂等前缀参数，默认值保持旧流程。新调用固定 domain/platform 1.2、growth 1.6、operations-base 1.2、currentInstallationRef=null、独立幂等键。maker/checker 分离保持。精确验证八工作台和三依赖边，不直接写 Installation 表。

新建控制执行器 scripts/a0v_ecommerce_1_6_first_install.py，只能连接既有隔离库，先验证旧实例已卸载及 canary=0，再创建 approved 安装并保存 Receipt。之后用既有当前成员权限和 RuntimeLifecycleService 请求 apply/verify；由唯一独立 Host 消费，控制器只读观察状态，不直接创建运行容器。失败保留 Operation/资源账本，不换键盲重试。

修改路径：scripts/a0v_canonical_ecommerce_first_install.py；新增上述执行器及对应 tests/extension_runtime 测试。出口：approved/active exact 安装 Receipt、宿主观察与资源清理/存活状态、负租户零变化。进入下一波 configure/enable、真实自然触发经营链验证。
