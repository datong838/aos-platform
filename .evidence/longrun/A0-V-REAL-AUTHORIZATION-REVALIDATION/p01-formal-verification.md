# P01 正式受控数据接入验证

2026-09-13 02:25 +08，代码基线80171540。范围为本地开发环境，非生产认证/发布验收。

正式接口已完成SourceSelection → RuntimeControl → 创建disabled计划 → exact绑定 → 启用 → 单次手动Run。计划sch-p01-qyh-controlled-20260913-v1，Run scr-4a7626db8f3d436e，10504ms，1行，succeeded，executor_stopped=true。02:23数据库复核原始Journal、derived记录与Dataset Receipt互相hash匹配，completion expected=1/projected=1/pending=0，SourceClaim仅1条call_ordinal=1；隔离租户看不到此Receipt。dataset为ri.aos.main.dataset.P01-shop-qyh。源查询范围ns_site/site_id=1、11字段、100行上限、30秒、maxSourceCalls=1；未改源库。这里不声称重复/恢复实测已完成。

当前user:dev持久化owner被DutySeparationRequiredError正确拒绝；实际成功主体为已存在的a0v-ecommerce-growth-1.4-runtime-owner，当前持久化admin经Owner全套校验后，通过已有本地开发令牌接口使用，令牌仅内存。没有改角色集合/成员，没有替换服务端actor。准备工具首次临时属性错误无源调用，失败证据保留。

API实际已加载80171540：18181、5173、8434入口健康；Host v15不重启，第二Host/Cron/模型自动任务/源预热关闭。生产Web元数据身份仍未收敛，不能发布。CUA实际打开5173/ontology与/data/schedules，页面可用，计划列表显示上述名称与02:21:08最近执行时间；未选择运行历史明细，不能据此声称完整交互验收。该浏览器侧栏显示“暂无可见工作台入口”，须继续核对当前scope与入口目录，不能忽略。

新增只读工具scripts/a0v_p01_current_preflight.py：固定当前安装/签名根与两个已存在主体，通过真实只读Owner路径自测；owner拒绝、admin通过（ns_site、11列、Shop）。没有新增产品执行逻辑，正式运行使用80171540既有产品路径。

下一波：先验证一次已成功Run不能恢复、控制调用额度不能被重复执行绕过，并核对源Claim与原始hash不增加；随后停用此验收计划以免留下过期启用计划（Cron仍关闭）。继续经营首链准备与经营参谋业务计划，核对八工作台入口。P01的Shop快照成功不等于真实数据更新自然触发Case/Run，更不等于八场景完成。
