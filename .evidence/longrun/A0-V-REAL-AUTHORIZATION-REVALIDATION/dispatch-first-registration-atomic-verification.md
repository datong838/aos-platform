# 受限首装原子登记隔离验收

2026-09-13，基线9b293106。代码为a0v_027_dispatch_first_registration.py及test_dispatch_first_registration_atomic_pg.py。主库未执行026/027迁移，未创建维护登录、未授予主库EXECUTE、未登记真实路由。

## 已验证

- RED：九项初始用例因新迁移不存在失败。
- 首轮九项通过：同事务完整九路由与Receipt、同请求重放、tenant/actor/binding/config/部分组/额外字段/marking拒绝、普通runtime无EXECUTE。
- 扩展测试发现数字idempotencyKey被JSON文本取值隐式转换（1 failed/15 passed），增加严格JSON字符串类型校验。
- 最终与026回执测试联合：27 passed（5.62s），7项既有警告。覆盖Python/SQL canonical hash一致、同key异请求/异actor拒绝、提交前故障整事务回滚、两并发组只有一组九项及一张Receipt、superuser session及非serializable调用拒绝。
- Alembic唯一head=a0v_027，diff检查通过。所有登记行legacy、fence=true、runtime引用null；不能执行经营Handler。

## 权限审查记录及未完成条件

该迁移是新增受限EXECUTE能力的实现提案，尚不是主库权限评审通过或部署回执。SECURITY DEFINER函数只授予专用maintainer；固定search_path和public限定对象，拒绝PUBLIC/runtime执行，拒绝superuser/bypassrls会话，检查采用角色及当前隔离级别，固定九操作，不接受SQL/handler/fence列表。真实主库runtime宽ACL未被本波利用或修复。

maintainer是受信任的控制服务身份。SQL函数校验安装角色/markings、当前安装/配置引用等存储条件，但不独立验证四来源业务配置和签名包声明。正式Owner必须调用生产预检并在同事务保留锁，固定当前请求身份，不能把函数公开给浏览器/模型。部署前仍须审阅这一权限边界、public schema CREATE权限、Owner与连接身份、API授权及撤销路径。

本轮fixture采用真实PG和迁移，但安装/配置基础表为最小结构、记录由测试Owner构造；并非完整签名安装、真实配置来源或真实业务链成功。重放当前要求目标仍匹配；目标变更后的历史Receipt读取接口、完整四来源Owner接线、首次fenced切换、未激活登记撤销/卸载尚待完成，因此不部署。

下一波先实现正式Owner事务衔接和独立权限复核：处理首次登记与重放的差异，不能在重放时被“空组”预检错误阻挡；确保原预检与登记使用同一受控事务，支持安全历史读取，随后接exact切换和撤销。
