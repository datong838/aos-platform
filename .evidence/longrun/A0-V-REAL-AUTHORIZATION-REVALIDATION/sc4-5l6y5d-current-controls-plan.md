# Y5d 十二路当前审批与停用组定义

2026-09-16，m1 aae57826，主库066，独立worker存活。沿用经营首链与Y5/Y6总方案：配置成为正式产品对象，为下一波共同窗口真实完整源组作准备，不以配置齐全代替业务成功。

## 1/6 当前前提

J d6531562-e388-4206-a3ba-a89aaddc255c / generation5295b81e-6005-4c2e-befc-3323f1456b8c，原Host12960保持。12管道/图/disabled schedule已存在；P03–P12 ingest为null，必须原PATCH改为pipeline-live-v1且enabled=false才能原Owner绑定。user:dev当前meta_membership为owner，接口Principal固定该身份，不伪造旧运行身份。

## 2/6 文件和执行设计

新增 scripts/a0v_snapshot_current_controls.py 与 services/aos-api/tests/test_snapshot_current_controls.py。固定租户、12 canonical pipelines和当前J；preflight由原Factory/CurrentRuntimeReleaseArtifacts/SourceConfigurationRevisionStore、原selections._guarded逐路共享锁核验，不源读取，事务Rollback。统一窗口由DB clock确定4小时，rowLimit1000、timeoutSeconds30、maxSourceCalls1，保留超限失败而非截断假完整。包/图/源配置/安装代次/epoch/配置ref全部精确绑定，读回旧selection/control latest predecessor和schedule binding，不根据历史总行数猜revision。冻结私有请求，不向日志输出凭据/客户记录。

## 3/6 原API登记

先PATCH十路live descriptor，保持disabled，以原持久化服务确认。selection→control→binding每步一个固定idempotency key，调用前冻结精确body/predecessor。无论响应成功或丢失均原账本独立读回并验证draft/actor/previousRef/hash；已存在intent只读回，不换键重发。无持久回执则停止该执行路径并排查明确原因。其他路径只做独立工作，不绕过不明结果。

## 4/6 停用组

全12当前绑定通过原group Owner共同窗口核验后，原PUT /v1/pipelines/snapshot-schedules/{uuid} 登记disabled组。当前签名SnapshotRelationshipPolicy v2原路径/精确hash，不手造关系。单定义、十二成员、完整租户、cron由产品定义，启用留下一波。本波不得开启调度或源读取。

## 5/6 验证

执行器新逻辑测试：确认回执前不推进、响应丢失只读回、未知intent不重发、actor/draft/ref不符拒绝；真实预检与逐项读回，最终12selection/control/binding、disabled定义与12成员对应。sourceRuns11/sourceClaims10不变，J/Host不变，worker持续空转；旧Case/Run不改写。

## 6/6 收口与后续

独立证据、主仓和两份开发上下文提交、Receipt。下一波Y6d受控启用完整源组，观察原调度Claim→SourceClaim→完整输入→Store/关系/原投影，超时/未知只回读，不能重读源或伪造旧snapshot。再处理Z原业务Run的正式恢复，推进自然经营链及八工作台持续观察。no push、230L0挂起。

## 预检纠正与执行入口

user:dev虽是工作区owner，但CurrentControlPermission要求安装控制admin/asset-installer，原门禁明确DutySeparationRequiredError。role映射不能根据名称推断，不放宽冻结权限。当前审批主体改用已有 a0v-ecommerce-growth-1.4-runtime-owner（原库admin），通过原PipelineControlServices/原SnapshotScheduleService登记（与接口同一事务Owner），不伪造HTTP身份。通用graph/schedule PATCH仍原产品API。另登记产品缺口：用户登录角色与安装控制角色的可配置衔接及真实用户审批验收，未完成之前不宣称零开发者接线整体完成。此波是已授权配置操作，不是伪造自然业务触发。

## 第4–6步：预检部分收口，登记依赖波次

实际管理员预检被原budget有效期拒绝：budget-policy@5有效至2026-09-16T06:29:53.243094Z；quota@1至2027-09-10有效。不是计费额度不足，不向用户重复索要费用许可。任何审批写入之前已拒绝，source Run11/Claim10、enabled0、definition0不变，见y5d-current-policy-preflight.json。

本波仅交付当前预检程序与单次提交读回保护（3 tests passed /3.24s；先缺helper收集RED再实现），未实现或执行十二路审批登记、组配置。文首3/6与4/6是保留的待办，不能记为完成。无live descriptor写入。预检只能产生短期候选，成功时才冻结私有preflight；失败没有创建预检文件。

下一波Y5e：正式模型证据更新、budget/runtimePolicy/model/route精确后继影响盘点，安装配置同代次更新/排空/验证/恢复路由方案。先新固定探针并只冻结续期方案，不直接发布全局新head造成J旧配置失效；核清现有原Run与原Host处理方式后再实施。随后恢复Y5d审批与组配置。新增真实用户owner角色与控制角色衔接缺口单独保留，冻结角色集合不改。
