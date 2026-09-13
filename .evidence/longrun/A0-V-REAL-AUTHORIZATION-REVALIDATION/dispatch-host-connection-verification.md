# Host 受限行锁与非特权连接验证

时间：2026-09-13T09:07:41.322607+08:00；基线77acea81，m1单写，不push。

## 实施
Host路由组读取改为固定public.extension_dispatch_lock_group_a0v_028(uuid)。默认连接与CanonicalRouter引用读取均复用独立runtime身份，不回退Web；写SERIALIZABLE，读只读REPEATABLE READ，事务内设置scope并校验非super/bypass/表拥有者以及FORCE RLS。保留Host的exact/fence/runtime行锁、权限、Receipt回读和显式commit。新增连接文件services/aos-api/aos_api/ecommerce_growth_runtime_connection.py。

## 新鲜验证
- RED：旧Host配028撤权与真实非特权LOGIN，3项均因直接FOR UPDATE权限不足失败。
- GREEN：Host单元、独立public数据库Host、CanonicalRouter、028受限锁联合56通过（13.34秒）。独立库使用原始028迁移、九操作组、非特权LOGIN采用aos_runtime和生产连接helper；验证提交、无效/伪造Receipt回滚、权限拒绝、canary不可见、只读写拒绝、超级用户拒绝。028已有并发更新阻塞和事务结束释放测试同跑。
- 启动/HTTP回归22通过（4.57秒），生命周期因OCI opt-in跳过1项；随后单独开启OCI复验，签名包安装/禁用/卸载重装/旧引用拒绝1通过（13.22秒）。合计79项通过，无未执行的所选测试。7项既有框架警告未改。
- 历史签名生命周期fixture仍是私有schema，其028与固定函数名在测试中映射schema，并改用非特权LOGIN；不将此映射当public原样部署证据，后者由独立Host数据库提供。
- AR2清册：1818模块/158分类/93迁移，五类错误为空。memoryctl validate GREEN，git diff --check通过。

## 限制与下一波
主库仍未应用026/027/028，新API/Host未重新加载，未新建真实登记或执行业务任务。当前连接构造要求专用runtime配置，未配置会拒绝；部署须一起核对现有身份文件、迁移、启动版本和主库ACL，不能先单独撤权。runtime_binding仍保留原行锁权限；全站Web超级用户风险尚未收敛。
下一波先补首次fenced登记的exact回执资格激活与未激活撤销方案/实现，再进行完整依赖登记-审批-激活验收及主库受控部署。自然首链、八场景、持续观察仍未完成。
