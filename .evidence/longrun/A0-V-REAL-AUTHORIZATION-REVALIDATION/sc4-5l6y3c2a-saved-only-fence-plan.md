# Y3c-2a 恢复专用配置禁止普通新读取

## 实施与验证结果（2026-09-16）

应用与066数据库围栏已实现。Red：恢复专用配置仍只被“原Run活动中”通用检查拒绝，未命中专用门禁（1 failed，10.59s）；Green：专用两项及原defined claim、execution guard共23 passed，34.56s。直接SQL重算request/record哈希仍被066 BEFORE INSERT明确拒绝，原十二Run/SourceClaim和历史回执不变。验证日志：`/tmp/aos-recovery-only-red.log`、`/tmp/aos-recovery-only-green.log`。`git diff --check`通过。

方案一致性：enabled不等于新读取许可；恢复标记缺Receipt也禁入，没有allowRecovery旁路。仅隔离数据库测试，本结果不表示恢复Owner、真实业务恢复或主库迁移完成。主库仍061；下一波实现当前权限包围的原输入历史事实核验，再接正式续期Owner。

规则：intent=renew_saved_group的持久配置版本只服务正式原input恢复；state=enabled不能被普通ScheduleClaim/SourceClaim当成新读取权威。Receipt尚不存在也应拒绝，避免“查不到恢复记录就按普通配置执行”。只读历史回执仍保留。

文件：新增services/aos-api/alembic/versions/a0v_066_snapshot_recovery_only_fence.py与tests/extension_runtime/test_snapshot_recovery_only_fence_pg.py；最小修改aos_api/pipeline_snapshot_schedule_claim.py的_lock_definition。此函数目前只供普通领取与普通SourceClaim守卫使用，读取exact当前definition后遇到renew_saved_group请求立即拒绝，不提供allowRecovery布尔旁路。C2/C3正式恢复须走独立RecoveryRef Owner，并重验原/当前两个身份，不能调用本普通准入函数强行放行。

066增加public.pipeline_snapshot_schedule_claim的BEFORE INSERT触发器，用tenant和exact definitionRef匹配持久definition revision的request.intent；恢复专用版本拒绝任何新header，即使调用方直接SQL并重算hash。旧历史行不重写，不删除，普通configure/enable版本行为不变。查询固定public且不对不可信resourceId做动态SQL或UUID强转。

验证复用C1b真实原输入/新控制的具名隔离夹具：应用领取新group在创建Run前即以recovery-only拒绝；原读取header和Receipt仍可查；直接SQLheader明确被066 BEFORE门禁拒绝而不是等到缺成员触发。原defined claim/guard/Receipt兼容回归。主库061不迁移、不调用真实源、不push、230L0挂起。完成后自动进入C2正式管理权限Owner与历史输入核验。
