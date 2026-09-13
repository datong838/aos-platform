# 路由权限与并发行锁审查 v2

2026-09-13，基线c7d5fe9f。结论：登记代码与连接已具备，但主库权限收敛不能直接REVOKE后宣布完成；须先替换Host的行锁入口。没有主库变更。

## 当前权威证据

08:03实际非特权runtime连接只读目录结果：dispatchRows=0、mutations=0。dispatch表owner为aos_app，FORCE RLS开启，runtime ACL含SELECT/INSERT/UPDATE/DELETE；无列级额外授权。aos_app为superuser/bypassrls/createrole/createdb；runtime、maintainer和当前runtime登录均非super/bypass。a0v_026表/027函数尚未部署。见dispatch-authority-current-acl-v2.json。

08:08 pg_default_acl：creator=aos_app/schema=public/table默认给aos_runtime SELECT/INSERT/UPDATE/DELETE。这与早期228ti2e6rls的ALTER DEFAULT PRIVILEGES定义一致。ar2_001建表后仅撤PUBLIC并追加runtime SELECT，没有撤掉默认继承的DML。隔离库重演证实该DDL组合确实留下runtime写权限。这解释当前现象，但未取得历史DDL执行日志，不宣称已证实具体执行时刻或恢复操作。

## 最小权限矩阵

| 主体/对象 | 当前情况 | 目标与依赖 |
|---|---|---|
| runtime→dispatch表 | SELECT/INSERT/UPDATE/DELETE | 只读；新增固定组行锁函数后再撤DML |
| maintainer→dispatch表 | SELECT | 保持只读；登记/切换只经固定受限函数 |
| runtime→登记Receipt | 026未部署；迁移显式先REVOKE再SELECT | 不可直接写，不可改删历史 |
| maintainer→027登记函数 | 未部署 | 专用非特权登录经Owner当前四来源与签名核验后调用 |
| Host→dispatch并发行锁 | 当前SELECT FOR UPDATE依赖UPDATE；旧PG测试额外授予UPDATE | 受限加锁读函数，同事务保留排他行锁、排序与漂移复核，不给普通角色直接改路由 |
| Host→runtime binding行锁 | 仍直接FOR UPDATE | 单列为运行控制表权限依赖；本切片不能宣称所有控制表只读化 |
| Web/原aos_app登录 | superuser/bypassrls | 生产身份收敛待单独落实；REVOKE不能限制superuser，禁止以新登记身份合格冒充Web身份合格 |

已部署cutover函数主要EXECUTE给maintainer；lifecycle fence/detach给runtime；两个history trigger函数保留PUBLIC EXECUTE（触发器函数不能作为普通SQL直接调用），本波不扩展修改其权限。完整函数目录见JSON，不把这一快照当泛化授权。

## 可执行后续切片

1. 新迁移a0v_028（实施前确认head）：固定参数cutover_group_id的加锁读取函数，scope来自已绑定GUC，固定public表，不接受SQL/表名/任意过滤；调用身份受控，返回有限路由字段，不修改路由、不启动Case/Run。
2. Host使用该函数持有同事务、相同排序的组行锁；原exact dispatch/runtime检查不减弱。测试真实非特权登录、跨租户、空/错组、锁互斥、事务回滚、禁用/切换竞争；不以给Host UPDATE权限绕过。
3. 同迁移显式撤销PUBLIC/runtime/maintainer对dispatch的直接DML，保留需要的SELECT及函数执行权；不能变更全schema默认ACL而误伤其他正常业务表。新表必须显式清理继承权限。
4. 验证固定027登记仍可原子写九项及回执、普通角色直写失败；然后首次fenced审批切换与未激活撤销/卸载完整性。未通过前不部署主库026/027/028或登记激活。

## 本波验证与限度

新增test_dispatch_default_privileges_pg.py：真实隔离PG复现默认DML遗留、撤权后SELECT成功/FOR UPDATE与UPDATE拒绝，1 passed（4.42s），7项既有警告。这是缺陷与修复依赖证据，**不是权限已修复或首链GREEN**。新增测试仅复演历史迁移，不修改历史迁移。主库没有权限变更或业务写入，m1串行、不push，230 L0挂起。
