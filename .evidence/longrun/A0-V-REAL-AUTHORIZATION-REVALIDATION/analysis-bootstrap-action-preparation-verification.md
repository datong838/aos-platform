# SC4-3c3d 专用初始化动作准备

2026-09-14，基线a73ee4d0。方案analysis-bootstrap-runtime-design.md。

新增AnalysisBootstrapActionPreparation与精确_BootstrapActionGuard，原Owner事务内创建原ActionProposal和草稿；守卫验证同一PG事务、原claim/来源/编译/Preview与当前身份，固定初始化payload/Task/Preview。ActionStore普通构造拒绝初始化动作，专用请求重新计算风险，回调后重复身份/对象复验和原Proposal回读。

执行策略仍R1 draftOnly。当前独立审批者也无法批准，未开始任何TaskRun。普通入口拒绝不是业务完成。

首次3项缺模块红测，实际草稿/重放/回滚绿测。追加普通入口、伪造风险、未启用策略审批拒绝；累计25 passed、7既有警告、13.78秒（/tmp/a0v-bootstrap-action-final.log）。原通用启动绕过测试改为明确注入已批准历史/损坏行，以验证启动门仍独立拒绝；新普通写入已被更早守卫阻断。

AR2 1903/181/93错误为空；memory GREEN AOS-000573。当前角色、Action注册及依赖为隔离库fixture，无主安装授权/数据改动，无模型调用。下一专用原子暂停启动门与审批承接策略整合，再接正式事件START；首链/八场景/观察未完成。
