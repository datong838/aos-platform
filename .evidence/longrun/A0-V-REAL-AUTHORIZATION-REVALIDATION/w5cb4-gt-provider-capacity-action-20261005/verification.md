# 独立 Owner 配置条款审批验证

基线 m1 0587746a/AOS-001347。仅原 Action maker/checker 批准申请条款，executionAllowed=false，不签发或激活物理容量。

- 原签名 Provider、原 EvidenceBundle 元数据、本地 HTTPS JWT、原申请 Store 生产后缺模块 RED：1 failed/7.18s，red.log。
- 原 maker 提案、禁止自批、独立当前 Owner 批准正向：1 passed/7.54s，green-r1.log。
- green-r3.log 的3项失败分别是 hash 冲突异常类别断言错误、Principal dataclass 复制方式错误，以及误把原期限 min 截断规则当拒绝。修测试驱动，明确继承原最终期限规则，不当业务反证或 GREEN。
- 督导发现原批准 replay 未绑定 checker：实际 A批准→B独立Owner同key/body 得成功，1 failed/7.40s DID NOT RAISE，checker-replay-red.log。最小在原 decide 同事务读 actor_id，仅专用容量 Action 拒绝错 checker，普通 Action 语义不变。
- 四文件回归90 passed/85.62s（adjacent-r2.log）；原通用 Action/Policy 相邻17 passed/19.62s（original-action-regression.log）；最后20项专项32.61s（final-special.log），含真实自然到期后拒绝。
- 实际 Owner 角色/Provider head/basis revoke/元数据变化、错proposal hash/跨scope拒绝，批准事件与预算容量数量不变；同checker重放仅一原事件，非maker提案拒绝；最终ApprovalEvent期限不超申请；非OIDC/naive/过长提案拒绝；原执行服务不能取得lease。
- 三种policy/binding/hash故障为原实际proposal读取后在内存修改行再调用原guard，只证明该guard拒绝，不冒充数据库维护写入或真实持久漂移。
- 五文件编译、精确diff纳入Delivery。无页面变更，浏览器验收不适用。全部PG自动disposable 5433；无当前库访问、迁移或重启。

原Action提案/批准事件/幂等/期限截断/通用执行禁入复用；新增guard强制完整DTO与SQL canonical hash、server maker、请求固定false身份、当前DB Owner、原exact Provider及head SHARE、原frozen未撤回basis、元数据/policy/draft/binding一致。专用metadata为保留入口，不允许runtime覆盖。

Source在申请审批阶段只作同conn元数据读，未关闭revoke提交并发窗口；发行/激活/执行必须另闭合Source epoch当前性。直接runtime SQL记录不证明OIDC maker、现有runtime事件不代替受限签发证书；正式issuer须核完整来源和独立身份。Evidence fixture含test-only事实；Owner申请数量及客户端账户ID不证明supplier物理限额或稳定账户映射。

督导受邀只读复审发现回放身份与期限规则问题并推动验证，不当后台自主值班验收。supplier依据、账户映射、NOLOGIN签发消费、共享账本/旧占用切换/一次Intent、transport/Usage/Report/Gate及b90完整八事实实际COMMIT/API/ToolBinding均未完成。自然首链、八工作台、观察、发布保持pending。m1单写/no push；无Host/worker/现实Provider/Secret/商城源/旧Run/manual/230L0/未知重发/外部效果。
