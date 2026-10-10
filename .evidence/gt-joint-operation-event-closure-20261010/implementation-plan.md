# 原联合结束协议：操作事件闭包

Rules：231/joint §11.3、当前AOS-001685、m1单写、原数据库READONLY。依前波真实目录与原native写入源码。候选①完整结束事件/触发影响合同；②正式Root/WAL期限裁决。先①，Goal不缩减，不修改已发布迁移/原deny/权限/数据。

文件：aos_api/aip_physical_capacity_joint_events.py、tests/aip/test_physical_capacity_joint_events.py及本Task证据。上波旧catalog组件保守全连通图仍作为目录上界，不修改其已Delivery文件。当前风险+metadata19表119triggers16func，加入原预算写入后双向FK扩436表2975trigger；不能把被查询/锁定的表当作写入再触发业务函数。先正式Task/Lease。

设计：输入受审查安装目录、真实原caller写操作种子(INSERT/UPDATE/DELETE/TRUNCATE)、FK原动作和准确trigger事件掩码、已人工审查精确bodyhash函数影响合同。不可变输入；外键引用检查仅新增read/lock依赖，不触发被引用表函数；父UPDATE/DELETE的incoming NO ACTION/RESTRICT也只查询/锁child，CASCADE或SET NULL/DEFAULT才产生child对应写事件。UPDATE缺column细节时保守按可能key变更处理，不静默忽略cascade。应用函数按实际触发操作匹配，其影响写事件迭代到不动点，循环安全；缺effect/禁用/hash漂移/未知relation或操作/重复目录严格拒绝。

效果合同语义/原PG内核binary/Owner/ACL须独立正式审阅，runtime DTO不充权威。内部纯组件不SQL/SET/COMMIT/权限/Root信任，不提供全Goal通过；输出仅原可能事件闭包+readlocks+必须检查constraint/trigger，executionAllowed不可初始化true。它仍是合同上界非数据库实际排队观测，完整finalizer需预算/Source/唯一Intent/currentness/clock/WAL。

RED模块missing；GREEN：引用FK不触发parent，父NOACTION不触发child，级联/SET NULL/DEFAULT后续完整链，trigger跨表写递归/循环，按op匹配，漂移/缺合同/disabled/未知/重复拒绝。原风险/metadata16函数真实body只读核；PG16.14官方ri_triggers源码用于内核语义阅读，不据源文件宣称当前binary谱系已受信。相邻旧catalog/prepare/reader测试；真实catalog缺完整effect拒绝。浏览器不适用；保留失败与证据，精准提交和权威同步后继续effects完整审阅。

实现前补充：TRUNCATE关联外键的CASCADE/RESTRICT是另一个正式协议，不在本joint正常启动操作中；本组件有FK关联时严格拒绝TRUNCATE。UPDATE未给column证据保守视可能改变父key；trigger WHEN不据假定false删除。复用原pure目录校验helpers，不改已Delivery组件。
