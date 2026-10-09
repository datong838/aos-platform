# v3 私有身份元数据必要门复审

遵循本目录 implementation-plan.md、231 与单写规则。仅新增 aip_model_shared_parent_certificate_identity.py 和对应 PG 测试；旧 v1/v2、迁移、运行入口和权限未修改。显式隔离安装不可作为上线迁移或身份授权。

完整 manifest/证书/root 原始字节、列头与 hash 校验后，复用 root→certificate 锁，再锁全域 identity；撤回、key/purpose 重绑与复活不能绕过旧全域身份门。新 immutable/FORCE RLS 表从证书导出字段，运行身份无读写权限。注册的 INSERT 和 identity 版本变化使用调用者事务内保存点，后置真实时间失败撤销子操作，调用者仍掌握外层事务。

当前两个文件 SHA 与 pure-result.json、native-r6/result-r6.json 冻结 SHA 一致。333 项纯验通过（1.19 秒），禁止全部数据库连接。R6 完整原 Source、Suite 两 case 四 leg 原生节点通过（125.56 秒），20 项反例、共享锁阻挡撤回与跨证书到期等待均通过。dual-wait-graph.json 记录 registration 26302→reader 26301→blocker 26300；失败注册异常后调用者真实 COMMIT，独立回读 failed-registration 证书 binding=0，测试核 identity 版本未变化。

独立只读回读 cluster 7694680278363095064 / aos_test_ae3180ed8baa_ti4_test：元数据事务 committed；风险与等待消费者 aborted，四风险表均 0；失败注册调用事务 committed。保留 2 root/5 certificate/4 新 binding（额外 root/cert 为拒绝窗口实验历史），旧 v1 binding=0、Source=1；trigger SECURITY INVOKER，runtime SELECT/INSERT=false。原保护文件 before/after 相同。

R1 CASE 解析、R2 tenant DTO 跨类型比较及 R5 单 blocker 观测假设失败均保留。R3/R4 是当时源码矩阵通过，精确源码冻结；R6 是修复保存点与双等待观测后的最终验证，不能以 R3/R4 覆盖最终代码。未重放失败窗口或未知外部效果。原 50 秒批准样例失败仍保留，新 100 秒批准是独立原件；旧两实验摘要 before-image 仍未恢复。

必要门的边界：实验 root bootstrap hash 未证明权威谱系；客户端 full description 的签名/hash 不证明当前 physical 准备态 DB 行及原调用者身份。独立元数据事务 committed 与风险 aborted 不构成同事务最终准入。合成 rebind/revive/deadline 证书只证明元数据负门，不能当新的 physical 原件。真实 Source/审批当前性、最终 joint、真实 token、WAL/ACK/transport 与正式经营首链仍待接线验收。execution_allowed、root_provenance_verified、physical_description_origin_authenticated、full_task_delivered、historical_fixture_restored 均为 false。

无 UI 改动，浏览器不适用。Prime 原未知请求未重发，本记录是代码/方案人工复审与原生验证，不宣称独立 Prime PASS。Task 保持 ACTIVE，不签全任务 Delivery、不改变业务 last-green/next-gate，不授正式库或 Provider 权限。下一已登记候选为原准备态行/同 caller 必要桥，以及 issuer bootstrap 谱系只读调查；actual token/joint 继续受真实输入和严格时刻语义约束。
