# UQ3-F 具体消费者贯穿验证

2026-09-13，基线c630ece6。RuntimeUiReadConsumer分prepare/invoke/finish；独立idle运行连接+REPEATABLE READ+7表FORCE RLS，当前成员/签名模块/包hash/快照/claim同事务准备，IPC事务外且绑定原PreparedJob，完成前当前权限及结果scope/cutoff/count/truncated/无执行许可再核验。目录仅枚举同租户活实例。准备与完成门禁采用局部回滚点，数据库撤权拒绝不会污染后续失败封存事务。

本进程带锁签发登记在prepare提交后建立，invoke只原子消费一次，finish提交后移除。旧对象、其他消费者对象、并发重复invoke和结果不明均不会重放。结果校验失败或撤权丢弃result，封存现有Attempt；新增READ_OUTCOME_UNKNOWN固定错误码。

28 passed、7项既有warning：11项消费者真实非超级PG、7目录、10领取封存回归。覆盖1 Case/1 Run完整纯投影、IPC期间无活跃数据库事务、重复/并发调用拒绝、准备拒绝无Attempt、撤权/错租户/未知/快照修改不交付、不可先封存后调用、跨消费者领取拒绝、丢失FORCE RLS在领取前阻断。

测试边界：签名目录和安装baseline输出为独立验证过的协议替身，PreparedJob调用替身执行实际包纯投影；真实数据库权限、RLS、canonical数据、Attempt和封存均执行。不是实际OCI只读方法交付，更不是栖月汇业务首链。首轮因测试连接代理不被既有真实Connection识别而没有绑定scope，守卫拒绝；改用真实psycopg.Connection子类仅重定位schema函数名后通过，未放松生产守卫。

主库仍未迁移、原宿主未重启。下一波UQ3-G接RuntimeHost：准备/调用/封存间复核同一assignment，撤销后不继续调用或交付；stop等待已开始调用，复用原生命周期排空，不能新起第二个宿主。
