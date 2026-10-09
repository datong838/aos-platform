# 原待签准备首门诊断与未闭合布局
Rules：用户AGENTS、AOS工程交付、231、原Source S01–S20。基线28e0f919/AOS-001635，原Source Task精确scope有效，产品/当前库/旧容器不改。
r1完整原两个入口1pass1fail19.57s：原材料登记通过，待签prepare42883公有未显式安装。原默认private设计不改变。最小测试接线为原exact_public_source_caller，shared/distinct完整参数及每节点独立库，保留签名原材料、JWT不入SQL、request hash、事务xid/backend、execution false、待签回滚断言。
r2接线引入显式transaction禁止显式rollback的错误1fail15.25s，原失败保留，修复force_rollback=True。不修改产品、不弱化回滚语义。r3 shared原完整项1pass15.60s，独立只读复核hash/cluster/完整函数ACL锁审计、五publication表零Source、roles NOLOGIN、临时接口清理、31旧容器身份/启动/挂载/端口全部符合。
distinct尚未执行、没有两布局绿色。当前盘剩2514800640 bytes，新库按80000000 bytes预算将突破2500000000保留门，禁止继续创建/删除历史库或重放同一冻结结果。资源局部限制不改Goal，后续需独立容量计划；最终COMMIT时钟真实反例仍未解。仅交付本有界首门诊断，原Source Task保持ACTIVE，全Source/首链/Model review无PASS。既有原测试fixture6/1不提交、无push、无系统重启。下一安全步骤是容量合同和原待签fixture其余调用者静态审计，不能以单布局代替原完整验收。
