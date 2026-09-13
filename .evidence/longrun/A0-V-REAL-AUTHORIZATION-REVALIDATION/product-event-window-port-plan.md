# BG-02 已安装核心包事件窗口端口

基线a2098ed2。新增services/aos-api/aos_api/ecommerce_product_event_window_port.py，仅接受精确CurrentInstalledPackageInvoker且package_id=domain.ecommerce.core，固定operation ecommerce_core_product_event_windows，无任意callback/源码import/重试。当前invoker自身执行调用前后安装/运行时/PreparedJob校验，后继消费者还须在最终写事务重读同一安装快照。

发送固定最多100项metadata信封，先严格校验schema、时区、日期范围、事件键唯一、时长。深拷贝输入，固定requestHash，调用一次。返回必须固定schema/hash/有序相同事件键，UTC秒级deadline且不超过策略截止、源新鲜上限和恢复上限；此为平台安全上限，不替代域具体算法。返回不含approved/enabled/业务载荷。超时/错包/格式/结果漂移均抛错，不commit、不重试。测试用精确invoker类的显式替身，不声称真实OCI运行。

新增tests/extension_runtime/test_product_event_window_port.py，验证篡改/重排/延期/bool/错包/异步一次/输入隔离；回归既有installed invoker。下一项三阶段消费Owner，将原批次/当前策略/当前启用回执/当前安装完整快照重新验证后落任务。
