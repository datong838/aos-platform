# Provider 未批准容量申请阶段验证

基线 m1 58a7e051 / AOS-001346。仅新增不可执行配置申请来源，不授额度或发送许可。

## 实际证据

- 原签名 Guard/Provider producer、原 EvidenceBundle build、实际本地 HTTPS JWT 验签后，缺模块 RED 1 failed/7.67s（red.log）；这是新增功能缺失，不是业务失效反例。
- 首次迁移误用 SQL 保留字 authorization，11 ERROR 未进入测试；修 authorization_mode 后 11 passed/7.63s。green.log 保留本地，错误不算 GREEN。
- 补实际 Owner/actor 绑定、Provider/basis hash/head/revoke、过期及 mutated DTO、runtime/维护角色不可改删、RLS flags/固定非执行 CHECK，20 passed/18.53s（green-r4.log）。
- 督导发现 runtime 直接 INSERT 绕过完整 schema 与正向 tenant；合法 hash SQL 反例 4 failed/11.55s DID NOT RAISE（sql-boundary-red.log）。a145 补 JSON 白名单、必填类型范围、aware 窗口与正向 tenant CHECK。拼接运算优先级错误导致 green-r5.log 24 ERROR；修括号后 24 passed/24.29s（green-r6.log）。ERROR 不算 RED。
- 督导复查 btrim 与 Python strip 差异；tab/newline/全角空格三例真实 SQL RED 3 failed/10.28s（canonical-boundary-red.log），a145 对 ID/key/maker/account/ref ID 使用完整显式 strip 空白集合。
- 最终六文件 77 passed、2 strict xfailed、76.46s（adjacent-r3.log）；本专项 36 项全部通过。原并发容量和 Model 申请、预算回归保留。两项 xfail 仍是物理容量权威与跨池共享账本缺口。
- 四文件编译成功，精确暂存 diff 检查纳入 Delivery。PG 全部为自动 disposable 测试库 5433；当前 a0v_142 库无查询、迁移或重启。

## 一致性及限制

Store 核同租户原 OIDC/当前 Owner、SERIAL/aos_runtime/GUC、Provider head SHARE 与 canonical payload、原 exact frozen 未撤回 Evidence 元数据、DB 时钟；hash 绑定完整条款和 server maker。重放不续期，actor/条款或依赖漂移拒绝。新表不可变、FORCE RLS、runtime 仅 SELECT/INSERT，basisVerified/executionAllowed 固定 false。无普通算法、预算容量占额或 Intent 改动。

Provider fixture 走真实签名 producer；Evidence fixture 包含 test-only Task 事实，原 Bundle build 只证明元数据协议，不能证明供应商容量、真实经营 Source 或依据适用性。账户与数量仍是 Owner 申请条款。SQL 记录本身不证明 OIDC maker 身份；后继独立 checker 须完整 reparse/hash 及原身份/当前依赖重验。申请阶段没有执行级 Source epoch 保护，发行、激活和执行必须另闭合当前性。

受邀只读督导两轮发现推动实际修复，最终代码复核认可并以本次终结 GREEN 为关闭条件；不当后台自主值班验收。Agnes 429 阻断保留。

独立 checker、supplier basis、稳定账户映射、NOLOGIN 签发消费、共享 occupation、旧占用正式切换、预算容量与一次 Intent 原子性、transport/Usage/Report/Gate、b90 signed 八事实真正 COMMIT/API/ToolBinding 未完成。自然首链、八工作台、观察、发布仍 pending。m1 单写/no push，无 Host/worker/现实 Provider/Secret/商城源/旧 Run/manual/230 L0/未知重发/外部效果。
