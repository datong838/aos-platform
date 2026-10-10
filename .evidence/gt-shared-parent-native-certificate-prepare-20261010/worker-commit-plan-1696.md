# 原提交前置与未知结果风险原生补验

Rules：231；joint方案§11.3；单写；先方案；已知失败不重发；真库只读。
候选一：原worker独立可见COMMITTED请求与风险、防重发，已有授权证据scope，依赖当前隔离PG；本轮先做。
候选二：完整native触发器effect可信来源绑定，已登记，依赖部署原生artifact来源与精确队列审计，保持pending。

精确新增文件均在 .evidence/gt-shared-parent-native-certificate-prepare-20261010：本方案、test-worker-commit-1696.py、run-worker-commit-1696.py、attempt/result/proof/review。产品源码和原测试只读不改。
复用原五worker、两consumer测试并添加两种真实状态机补验。新随机全迁移保留测试库，test-owned reduced预算schema；合成callback，无网络Provider。独立连接在callback中FOR UPDATE NOWAIT并读取xmin状态，原submit请求ref非空，三桶风险从held转submitted且守恒。超时转unknown、结果持久化失败保持submitted，独立回读风险不减少；再调用返回RECONCILE_ONLY且调用计数仍1。测试失败落盘，不重放旧attempt或清理库卷。
局限：只能证明普通Content执行primitive，不证明v3物理风险/双父证书联合COMMIT、正式身份、实际Usage或自然首链；不据此悄然拆分已批准原子合同。成功后复审，并同步CAS与checkpoint。
