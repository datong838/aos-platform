# Source 专用独立候选条款批准验证

基线 m1 10471542 / AOS-001349。本波只交付完整候选条款的独立 Owner 审查，不签发正式 Source 或授予容量。

原签名 Provider、原 Evidence、本地 HTTPS OIDC maker/checker、实际 account/basis 候选与原 allocation approval 全部形成后，新增入口缺模块实际 RED 1 failed/7.42秒（red.log），初步正向1passed/7.29秒（green-r1.log）。原event版本1/currentproposal版本2正向实际确认。专项首轮23passed/34.65秒（special-r2.log）。

加入原执行lease拒绝及metadata保护/canary检查后五文件实际123passed/109.67秒（adjacent-r3.log），含Source专用审批、候选契约/producer、原申请和原独立审批。最后新增真实自然到期拒绝，Source26项与三个原通用Action/Policy文件合计40passed/55.39秒（final-special-original.log）。编译和git diff --check通过。各日志只用于对应已收集测试范围；没有把23项或123项声称覆盖后加的自然到期测试。

专用 guard复用原draft/policy/binding/当前Owner/maker-checker规则；原guard默认值保持不变。新metadata有runtime写保护，R2/makerChecker/executionAllowed=false；generic入口缺exactSourceGuard拒绝，错checker同key/body不返回别人原成功。Source候选tenant/fullDTO/账户与basis精确hash和原canonical envelope/server maker均核验。账户声明必须匹配原申请、完整Provider exact包含且head当前，basis并发不超原申请；Source validity和提案expiry不超basis/原request/旧批准期限。

旧批准只接受唯一approved事件v1/currentproposalv2；事件完整原snapshot canonical hash、proposal hash、原policy/binding/slot/eligibility和当前独立Owner同conn复核。实际追加第二批准和后续拒绝均使Source审批拒绝。实际accountID变化、并发升额、basis错账户、四类hash、未来窗口/过长期限、formal类型native变异、非OIDC/canary、Owner角色、Provider head、Evidence撤回、metadata漂移均拒绝且无新增proposal或审批效果。samechecker replay幂等；原预算与容量占额不增加。自然到期等待2.1秒后原审批前guard拒绝，原执行服务无法取得lease。

督导只读方案复审先提出版本关系和账户/并发约束，先补方案再实现；代码复审确认一致、无新阻断。受邀复审不作后台自主值班。未来/陈旧 observedAt、供应商实际窗口与真实归属仍由issuer特定政策验证，本波不自行选择未知时效政策。

所有PG为自动disposable5433，无页面修改，浏览器验收不适用。当前142真库无访问/迁移/重启；无Host/worker/现实Provider/Secret/商城源/旧Run/manual/230L0/未知重发/外部效果。m1单写/no push。

审批仍是claim条款，不证明supplier事实。runtime原候选/审批行不证明受限签名来源，Source元数据读取未闭合revoke提交epoch竞争。正式账户双向归一、跨tenant同真实账号约束、供应商来源适用性/时效、受限issuer/消费器/非执行正式签名Revision继续属于完整SourceTask，保持ACTIVE；共享occupation/旧占用切换/一次Intent/transport/Usage/Report/Gate、b90完整八facts实际COMMIT/API/ToolBinding及自然首链/八工作台/观察发布继续pending。
