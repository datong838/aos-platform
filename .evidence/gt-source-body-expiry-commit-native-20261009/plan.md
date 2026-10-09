# 原 Source 自身有效期越过后的实际提交观察

基线881c65e5/AOS-001628，原最终COMMIT合同继续。候选①真实body valid_until跨越提交证据；候选②独立review入口恢复待daemon支持。选①。当前仅此原生进程，前JWT诊断进程已退出。

沿前已验证原fixture/逐布局全迁移bootstrap/原private签名/原SERIAL SCRAM/public prepare/sign/finalize。真实fixture JWT exp设当前+700秒，仍实际签名并经原验证，不写未验证authentication；此举仅让JWT覆盖真实Source body约5分钟窗口，不改任何审批/basis/permit/Source有效期。finalize必须在两deadline前，等待原数据库clock越过Source.valid_until+0.1且JWT仍有效；实际callerCOMMIT一次记录原生接受/拒绝，未知结果先只读对账不重发。观测最长360秒，每1秒读数据库并等待<=1秒；可响应并保留中间证据。

本轮先shared完整真实caller观察，distinct已登记后续；不把单布局代表双布局，也不把测试成功代表最终时间语义被批准/修复。完整Source/epoch/legacy任务仍ACTIVE。记录原nativexid/pid/dbUTC/两deadline/hash，无JWT/key；提交后的消费者当前性单独后续，不能以这次签发提交充作执行授权。独立Source signature/hash/provenance/xid/角色及原31资源核对；所有保留库不删，不改当前权威库/产品/服务/Provider。无需浏览器。

实际r1主体PASS、teardown ERROR：原fixture清理临时接口后再次检查已过期的签发输入，原检查抛出固定拒绝，而fixture只接受返回false。保留原日志与结果，不重放COMMIT、不将pytest退出1改为0。下一步仅修改本目录verify_native.py：分别断言主体passed与teardown failed，独立只读核对持久化、角色和临时接口恢复；报告观察成立及清理断言失败并列，不宣称完整测试通过。产品和原fixture不修改。
