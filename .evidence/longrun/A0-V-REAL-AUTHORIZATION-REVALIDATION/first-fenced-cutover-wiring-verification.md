# 首次禁入登记切换接线（待完整复验）

2026-09-13T10:29:57.141605+08:00，基线a40a67a5。
Cutover构造可选exact登记Owner，缺配置继续拒绝首次ref；prepare要求legacy/fenced且revision1，通过存储来源/目标/当前资产与签名核验。pause/commit/validate/resume在原exact运行阶段校验后重新核验，当前actor传递且同事务runtime→maintainer；回滚恢复原禁入快照并保留原审批/Receipt。Owner新增固定资产来源入口，runtimeStateValidated=false，不冒充阶段授权。正式HTTP/启动仍未配置，主库无新路由。

## 验证事实
新增首次fenced PG编排用例正向及各阶段拒绝、旧审批不含ref拒绝、当前资产撤销后rollback恢复fence=true。当前资产Owner节点在Cutover PG中明确替身，实际存储/配置/签名分别沿已有Owner与资格测试；不称全依赖正式验收。
最终联合运行107项：106通过、1失败（29.15秒）。失败为既有签名OCI生命周期health observation is stale or in the future；独立复验同一错误1失败（6.56秒）。不能汇报107全绿。初始RED因重启后测试基库5433未启动及测试角色缺失未进入业务断言，后改显式18432独立测试基库并补测试NOLOGIN角色；不把环境错误充作实现RED。
诊断：18432数据库clock_timestamp相对宿主约-0.072秒；colima timedatectl显示System clock synchronized=no、NTP active但Packet count=0。当前verification_commit._fresh_health要求0≤数据库当前时间-宿主观测时间≤3秒，跨时钟会拒绝。该代码本波未改，不放宽3秒或未来拒绝。下一波将健康观测锚点取自同一数据库权威时钟，并用探测前锚点避免延长新鲜度，单独方案测试后复验本波。
清册1819/158/93五类错误为空，diff-check通过。

## 重启恢复实况
原Colima/数据库已启动。18181/v1/health、/v1/ready及5173/ontology均200。API保持迁移禁用、业务Cron/自动模型关闭。运行Host已启动PID4753，但当前generation23afd05b-762c-406a-adfb-247a14412b9f实际变为revision5/epoch4/disabled/fenced/unknown；租约30条全部released。主库仍a0v_025，经营dispatch0。旧generation/配置授权不复用；不能声称全系统业务就绪。8434旧入口未恢复。
当前实现提交仅供接续，未部署主库迁移或首次激活。下一波健康时钟修复和真实实例受控恢复优先，再未激活撤销与完整依赖首次登记激活。
