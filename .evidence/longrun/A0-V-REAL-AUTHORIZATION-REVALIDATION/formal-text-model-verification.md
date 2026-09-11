# 开发文本模型与路由发布验证

2026-09-11，北京时间12:40，基线dee07eb1，m1串行。任务A0V-FORMAL-TEXT-MODEL-20260911。

先在完整升级的自有隔离库aos_upgrade_check_f1dc452abade执行冻结计划，再重放两次，518表行数不变、exact引用相同。新增当前Provider/Network状态及有效期核验后再重放通过。拒绝测试先复现4项未拒绝，再修复；5项发布边界+14项历史证据测试共19通过。已有Pydantic/Starlette警告和退出JDBC日志关闭异常仍在，不影响测试退出0。

实际恢复库aos_meta_head写入前新备份4553022字节，SHA256 e556bac243672c2401bd36299850fda72364386ee51fa849756c1bb237f888fa。备份保存在受限本地目录/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/state/a0v-formal-text-model-20260911/before-publication.dump，不提交客户备份或凭据。

冻结计划8b15d69d03d89ba62c095c4d9abf6315e6f25b62c5d3f3c762b56848ad9165ed，两库均从正式Runner报告经Release服务推导各自Gate，不跨库复制Gate。实际新增Dataset1、Suite2、EvalRun2、Report2、Gate2、Model1、Route1、Price1、BudgetPolicy新revision1、RuntimePolicy新revision1及Owner Receipt。其他表行数不变，448张含双租户列的表中canary行数全部不变；主库再次重放零新增，exact引用相同。计数核验不是全表内容哈希证明，也不是非Owner连接RLS测试。

- RegisteredModel a0v-agnes-2-5-flash-readonly-dev r1，hash 54d69d88eb22d34bbf7678b69d0678007fc2f2d3dfb0be6116cc9e68e3d72606。
- ModelRoute a0v-ecommerce-text-readonly-v1 r1，hash a5e9b83110743d53a8739ddd55f9ff0c8f4609bef99e5425da389c0692ef7998，仅chat.answer。
- 开发价格数字保持null，授权到2026-09-11T17:38:54.448609Z（北京时间次日01:38:54）；成本未核定，不当作免费。

重要边界：模型评测是三份已完成探针的历史可信本地元数据核验，保留原观察时间；不能重新证明未保留的回答全文，也不是本波重新调用已注册模型。路由评测仅文本任务配置接受/视频音频拒绝，不是经营内容质量验收。发布过程中Provider调用0、业务Run0。原健康已经过期；结果明确NOT_CHECKED，不开启自动调度或扩展，不宣称业务就绪。

计划和实现一致：Owner幂等/CAS、未知EvalRun无Report拒绝重造、当期Provider/Network和开发预算/价格核验、同计划重放。尚存运行时撤销并发窗口由后续Host锁/epoch处理；脚本是受信本地显式调用入口，不提供公网参数入口。

下一波：补足Agent职责所需技能发布与文本能力绑定，验证候选安装schema011兼容并激活现有approved安装；随后真实门店来源、经营参谋首次分析入口、自然事件接线与内容任务续跑。真实经营业务计划、首链、八工作台场景、连续观察和发布决定均尚未完成。API仍运行1100b936，需准确重载；不push，230 L0挂起。
