# 内容执行日志 PostgreSQL 验证

Task A0V-CONTENT-EXECUTION-JOURNAL，基线 ea77abb4。

新增 a0v_003 两张命令/结果不可变日志及事务绑定 Store。预算 reservation 是发送状态唯一权威；日志没有并行状态字段。scope+reservation 主键和外键、RLS、数据库状态/请求ref触发器、读回hash、same replay/drift rejection 已实现；不提供自动调用或API。

首次测试 collection 报模块缺失，随后完成实现。在 colima-aos-extension 的 aos-a0v-recovery-pg 中，仅随机隔离 schema 执行迁移。首次数据库场景通过；扩充并发测试曾因同一 fixture 下申请第二笔预算超过原有 daily limit 而失败，代码未绕过预算，改为两连接竞争第一笔同一 reservation，契合并发登记的验证目的。

最终运行 journal PG 场景与已有 cost_pending PG 场景：2 passed，exit=0。验证并发两次登记仅一条记录、新连接回读、命令与结果同内容回放、漂移拒绝、提交前不能记录结果、跨租户/伪传正scope不可见、缺scope拒绝、runtime更新删除权限拒绝、owner更新触发器拒绝、空schema可降级/重建、已有日志禁止降级。diff check通过。

连接凭据仅由既有容器连接助手读到进程内；无argv/env/log输出。AOS_DOTENV_DISABLED=1。测试清理自己的随机schema，public未升级、真实业务数据未改，Provider调用0。启动阶段既有schema warnings、pytest预导入warning仍存在。

边界：日志命令/normalized结果本身不是批准、Artifact或Usage权威。未来worker必须重新核验安装/dispatch/模型/来源，先持久化ProviderRequestReceipt再进行一次事务外调用，成功结果读回后由既有Owner生成Usage和Artifact。现有no-effect Host尚未接enqueue，用户不可通过日志API启动工作（无此API）。真实首链与八工作台未完成，authority不前移。
