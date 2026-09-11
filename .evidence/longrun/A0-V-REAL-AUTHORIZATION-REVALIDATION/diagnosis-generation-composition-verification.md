# D02 生成执行组合验证

2026-09-11；基线 m1 d3b5f2f5；任务 A0V-D02-GENERATION-COMPOSITION-20260911。对应 diagnosis-generation-composition-plan.md；六文件 SHA-256 见 diagnosis-generation-composition-files.json。

## 实现

DiagnosisGenerationService 将当前 D02 running AgentRun、完整来源、固定诊断请求、既有受控 Executor 和 DiagnosisReceiver 组合。调用前确认原文存储就绪；已有成功仅恢复，prepared/invoking/unknown/failed 均不自动再发。输入深拷贝，来源事务在网络执行前退出；调用后重新读时钟，恢复器再次核对当前来源。

复用接收器当前来源函数。材料增加 bundle.marking，仅用来控制请求分类，不进入固定模型请求，原始请求hash保持不变；同时检查正文 marking，不允许降级或推断未知级别。历史材料没有 bundle.marking 仍可解析恢复，新的执行入口缺此级别则拒绝。

## 验证

环境 AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1 AOS_GROWTH_DRAFT_OWNED_CLONE_TEST=1；项目 Python pytest 范围：

diagnosis_service、diagnosis_receiver、diagnosis_generation、analysis_proposal、analysis_sources、growth_plan_receiver、growth_plan_full_graph、authority_store、growth_plan_worker、growth_plan_generation 对应十个 test_ecommerce_analyst_*.py 文件。

**226 passed，7 个既有 warning，5.74 s，退出码0**。新增服务34项：固定请求、关闭事务后单次调用、十分钟慢调用后新时钟、等待中调用方修改无效、已有状态零重发、原身份漂移阻止恢复、分类不得低于包/正文、未知不发布。新增完整一次性 PostgreSQL 测试用原成功正文+真实Owner恢复诊断，明确 Executor 调用即失败，实际零调用。前波4组完整接收数据库及原D03关联回归通过。

早期两个命令漂移测试的命令与持久化替身共用嵌套对象，导致两个对象一起被改；把夹具命令深拷贝后正确验证预算和容量引用漂移拒绝，未放宽业务代码。退出后的既有JDBC日志关闭流提示不影响退出码。git diff --check通过。

## 边界与后续

真实首发模型路径此波为执行器替身，不是 Provider 实测。表图含合成事实/完成调用，不是栖月汇真实业务证据；无主库业务写入、无Provider、无API重载。来源检查是快照，不能保证外部调用与撤销原子；后续审批/执行仍须重验。未新增公开入口、AgentRun 创建、模型选择或批准。

下一波 D02 TAOR 工作者与前序画像交接，之后 D01 方法/指标权威、三阶段宿主/运行配置、真实数据与经营参谋首链、八工作台真实场景及观察。整体未完成，不push，230 L0挂起。
