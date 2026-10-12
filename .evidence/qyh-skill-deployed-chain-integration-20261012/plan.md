# 真实部署原型→连接→完整终结联测（隔离）

Rules：AGENTS.md、231、完整生产链/D-wave。上一权限原型是目录/权限守恒，不能证明真实RLS隔离。候选一正式Owner/配置来源待接入，候选二当前prototype实际与事务代码联测，选择二。仅修改test_skill_eval_atomic_finisher_pg.py，不改产品或真库。

标准UUID完整克隆fixture保留测试签名/数据初始化，移除手工finisher GRANT/宽FOR ALL policy；实际installer在aos_app/SERIALIZABLE/精确DB及cluster/schema161、role member0时执行并commit，之后才给新test LOGIN两角色。原caller完整终结、private connector、签名消费者、late rollback及并发全部在真正安装的6policy权限上运行。新增测试在仅实验内插入PUBLIC using(true)冲突，新的finisher restrictive双tenant仍保证canary读0/update0，合法scope能读；账本状态不改。管理员只做明确实验bootstrap，不在终结helper里切超级权限。代码调用/真实签名夹具是隔离，不等于正式发布/Owner预算/外部TargetJudge/八台首链。
