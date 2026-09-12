# Niushop 1.4.0 候选源验证

2026-09-12，基线 e8ada19e，m1 单人串行；按同目录 niushop-1.4-snapshot-candidate-plan.md 执行。

新增候选树 platform.ecommerce.niushop/1.4.0 和固定准备/构建入口。旧 1.3.0 树摘要仍为 sha256:f79374cef9fbd6c5a55e312b1e18f4bdaeabecb756d95128d82fc8eda28c73bd，新树 sha256:e819116f16f2c0e057fbbbbbcfba05e614ddafb2f312566c24dc07cb15244709。逐文件只有 bundle.yaml、content/mappings/p01-shop.yaml、evidence/bundle-evals.json 三处差异。P01 mapping 摘要 sha256:893691a4bd11d52f40da19a0435390a5beb2195e594dd19f506b80a90505f4bc。

新评估先置 pending，再实际验证映射编译、14 属性进入现有对象内核、明确观察时间、PII 列拒绝、其他店铺拒绝、重复源键拒绝；成功记录 static-snapshot-mapping-only 范围。准备过程不覆盖已有目标，不改变旧候选。独立 builder 模块实例选择平台 1.4.0，原入口默认仍为平台 1.3.0。

实测：test_niushop_snapshot_candidate.py、test_ecommerce_runtime_candidate_builder.py、test_pipeline_snapshot_materialization.py 合计 48 passed，7 条既有依赖告警；静态预检 4 包、3 运行成员、8 模块、12 操作，详见 niushop-1.4-source-preflight.json。AR2 ar2-7 闭包扫描 1801、分类 158、迁移 93，hashErrors、unclassifiedForwardDependencies、unclassifiedReverseCallers、bundleCrossLayerImports、dynamicReferenceErrors 均为空。记忆强投影 CURRENT，validate GREEN。

限制：本波只证明源候选和静态映射，不是 OCI 资格、发布、安装、当前授权或真实业务完成。合成对象评估未读取真实商城行，P01 未启用；旧 Host/API/安装保持原基线。当前新迁移 a0v_024 尚未部署到主库。静态评估导入已有模块出现 API 组装日志，未显式调用源库或 Provider。

下一波：在独立 colima-aos-extension 引擎和全新仓库外目录构建、执行真实 OCI 资格检查并固化输出摘要。随后准备正式新版本发布/安装配置路径和受控源占用提交后的单次读取入口。发布与真实首链不得从静态 passed 标签推断。230 L0 挂起，不 push。
