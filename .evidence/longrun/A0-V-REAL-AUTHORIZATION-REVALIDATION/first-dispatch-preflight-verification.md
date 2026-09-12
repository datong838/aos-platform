# 首装登记当前安装预检验收

2026-09-13 05:46；基线bc6df83d，主任务API租约内m1串行施工。

## 验证

- RED：新增预检模块未实现，测试收集ModuleNotFoundError。
- GREEN：登记契约与预检46 passed（4.35s）；7项既有警告及旧契约故意绕过构造测试产生的序列化警告。
- 05:44真实独立runtime连接采用aos_runtime，在org-org/dev-project调用生产PostgresInstallationStore和CurrentFourSourceConfigurationAuthorization；当前安装eda57424-b8cb-401e-a6f7-94220cb4f9ef@5及四来源配置校验成功。返回currentConfigurationValidated=true、authorityValidated=false、executable=false、businessWrites=0。
- 05:45真实负例：dev-org租户AssetNotFoundError；不存在actor的当前权限RuntimeConflict；binding/config revision漂移ValueError。结束回读dispatchCount=0。无新增源查询、无凭据输出、无业务写入。
- AR2清册1813扫描/158分类/93迁移，五类错误列表全空；git diff --check通过。

## 方案一致性与边界

新增服务只SELECT及事务锁，复用active lock摘要、当前安装CAS、配置内容hash及四来源权限，不复制授权状态机。不接受任意授权回调；原预览仍不是登记权。已有组拒绝分支已实现，实际部分组/并发组的隔离PG覆盖留给登记持久化阶段，本轮未在主库造测试路由。

当前仅确认安装、配置及空路由状态适合继续准备。尚未检查签名包九项声明的最终登记资格，未写登记Receipt、未新增权限、未挂HTTP、未激活路由。预检返回值不能用于随后跳过当前检查，也不能把此GREEN当作Case/Run自然首链成功。

下一波：对正式登记的受限数据库入口/不可变Receipt做权限评审和隔离PG实现；默认fenced、完整九项原子提交、重放与并发唯一、无权限直写拒绝。随后接exact审批切换和未激活登记卸载清理。
