## SC4-5l6d5a 原就绪计算入口（2026-09-14）

Rules：方案先行、m1串行、不push、230 L0挂起，保护已有用户改动。依赖顺序按snapshot-readiness-design.md先锁定d5接收合同，再做d4c当前安装事实。

新增source_readiness_snapshot_contracts.py和tests/test_source_readiness_snapshot.py；source_readiness.py增加evaluate_installed_snapshot，复用原对账、状态优先级及聚合合同。完整有序P01-P12、对象类型、同租户、带时区时间和精确ref/质量ruleRef校验；入口重新序列化校验，拒绝model_copy绕过。保留观察cutoff，未观察的projectedAt不伪造。原就绪过期边界从>改为>=，同时修正原原因列表并验证旧入口。

Red：新模块不存在的收集错误（/tmp/sc4-d5a-red.log）；Green：新测试27项+原服务3项+原合同3项，共33 passed / 7.38s（/tmp/sc4-d5a-green.log）。覆盖完整12、缺失/错序/重复/对象/租户、原质量失败/未知、实际对账缺失/差异、空、到期边界、时间与引用篡改及原入口回归。7项现有框架警告。AR2 ar2-7：1945模块/190分类/93迁移，全部错误列表为空（/tmp/sc4-d5a-closure.log）。

边界：纯合成输入验证不是当前安装授权、真实12源验收或Receipt。质量由后续原当前Owner填充；没有API受理自报ready，没有模型/源库调用、主库迁移、主Run/Task转换、发布安装或外部消息。缺计数按原对账算法FAILED，不虚构PASS。主环境版本与运行健康本波未刷新。package.json/package-lock.json的外部Playwright改动和overall-progress-20260913.md原+42行未纳入。

下一波SC4-5l6d4c：从当前安装、Source/Query/Quality/Business、基础对象计数及原Binding Owner构建完整12类输入，验证缺失/撤销/安装与事务后变化；随后d6原Receipt保存回读、l6e原状态恢复、l6f Outbox、l6g主环境及真实业务全链/八场景/观察。整体业务目标仍未完成。
