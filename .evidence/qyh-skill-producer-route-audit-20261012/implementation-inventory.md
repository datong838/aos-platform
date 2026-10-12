# 新Skill证明生产者实现清单（尚未实施）

原BG00u和BG00ac的后续范围：不能删除runner拒绝门或仅拼接writer。

|候选文件/原组件|要完成的行为|必需的真实依赖/验证|
|---|---|---|
|拟新增 aos_api/aip_signed_skill_eval_runner.py|独立Skill专用入口；解析原frozen EvalContract/Suite/脱敏Dataset精确hash，创建全新执行intent；每case执行一次目标与Judge，封装双证书/签名Receipt及真实结果|受信Root/独立target+judge签发身份、Owner/Scope、当前审批/预算/网络许可；不能复用旧Run或普通未签TargetExecution|
|原 aip_eval_writer_atomic.py / preflight|只消费已发生的精确签名结果，逐case预检后同事务Receipt/Report/Sidecar登记；保持拒绝缺依赖|独立配置Eval writer、原GRANT/RLS/Source权限分离，晚期失败全rollback；当前登记器不是执行器|
|原 aip_eval_writer_reconcile.py|连接或commit结果未知时只读对账，完整当前证明才COMPLETE；任何UNKNOWN不允许再执行或重发|数据库readonly repeatable snapshot、exactrefs、双方receipt/hash/撤回与有效期；部分行/未知结果须保持UNKNOWN|
|拟新增 tests/aip/test_signed_skill_eval_runner_pg.py|用全新隔离、真实签名及原suite/Run/Report路径验证完整生产链，禁止lambdaTrue/手工running或业务旧报告补签|RED、成功、Target/Judge拒绝、输入输出漂移、跨租户、预算不足、未知后不重发、晚期事务失败、并发幂等及明确不自动publish/start|
|原 runner/Skill发布/readiness|旧普通Logic/媒体路径保留；新Skill仅完整原证明通过后可原publish/evaluate，Model仍独立unsupported|相邻Logic/Media、Scope、原证据读取器与权威判断，真实新执行/权限先齐后接入口|

这些是后续实现候选，不是本波已写代码。新增实现须进一步冻结精确trusted-executor协议和Scope授权；当前实际target/judge签发Root与Owner/预算资料未知，不能把测试key当正式issuer、以普通回调返回值冒充真实执行。正式配置已请求路径，不能仅修改公开subject字符串完成独立认证。
