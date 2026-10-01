# BG00GQ 正式 Provider / 费用来源联合方案

基线：m1 76b0c599，AOS-001057；231-5 §1/2/4/6/7 与450接续。
Task：W5CB4-BG00GQ-FORMAL-PROVIDER-20261001。真实库只读，本波仅标准全迁移临时库。

## 缺口与目标

Budget prepared() 直接插 Provider head/revision，插件、出境与分类引用均占位；该测试来源不足以证明正式配置产品链。
替换为原插件 Authority 当前批准版本、签名 Guard maker/checker/低权消费、原认证 HTTP Provider 发布与 Receipt，再交给既有签名费用批准/消费/派生链。
无外部 Provider 调用；opaque secretRef 不证明真实凭据存在；无健康观察与 Eval 时不得制造 READY。

## 文件级实施顺序

1. tests/aip/test_formal_provider_cost_source_pg.py：RED 验证原发布 Receipt 和 exact 插件/Guard 来源。
2. tests/aip/_runtime_guard_history_fixture.py：复用惰性签名资源，追加原 Provider HTTP 生产入口；无鉴权 override，无直接 Provider 插表。
3. tests/aip/test_budget_cost_issuer_pg.py：prepared 改用上述生产入口；短时有效预算在来源准备后发布，保持有效期攻击测试真正检验目标。
4. 原费用 issuer/consumer/configuration 与 Guard/Quota/Model 累计回归；审查测试证据范围，不把隔离 identity 称为客户 authority。
5. verification、m1精确提交、AOS/Prime/D-waves 接续更新。

## 验收与风险

正式 Provider 有且只有一笔原发布 Receipt；插件来自当前 manifest/approval；两个 Guard 为真实 active2、可从原 Store exact 回读；费用链既有签名、撤销、过期、未知结果、并发测试不退化。
仅配置来源改造；完整 Model/Eval/Health/Review/AgentRun/首链继续未完成。签名临时角色与私有凭据文件不得互相覆盖；不碰现有其他 dirty，不迁移当前实例，不启 Host/worker，不读商城源、不回放旧12Run。
回滚仅本波精确代码提交；无当前业务数据变化。
