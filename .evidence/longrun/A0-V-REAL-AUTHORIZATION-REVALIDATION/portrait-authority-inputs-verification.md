# D01 正式输入元数据验证

2026-09-11，m1基线a18a606c，任务A0V-D01-AUTHORITY-INPUTS-20260911，AOS-000573。方案portrait-authority-inputs-plan.md，三代码文件pre/post hash见portrait-authority-inputs-files.json。

AipEvalAuthorityStore新增领域中立get_metric_definition，按租户/精确版本读取并校验拆列/正文身份。D01 read_portrait_authorities在同显式连接核对当前Method、唯一且最新的MetricDefinition、当前frozen且ready的EvalContract；重新计算定义/合同正文hash。额外读取绑定发布门的实际decided_at/expires_at/status/hash，拒绝过期门。没有把指标定义存在当成观察值或画像ready，也未改变原公共Eval readiness行为。

专项53 passed；扩大关联后**234 passed，7既有warning，8.63 s，退出码0**。环境AOS_DOTENV_DISABLED=1、AOS_TEST_USE_SHARED_DATABASE=1、AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1、AOS_GROWTH_DRAFT_OWNED_CLONE_TEST=1；范围12个test_ecommerce_analyst_*.py：portrait_sources、method_authority、authority_contracts、authority_store、diagnosis_worker、diagnosis_service、diagnosis_receiver、diagnosis_generation、growth_plan_receiver、growth_plan_generation、growth_plan_worker、growth_plan_full_graph。新输入29项，含3组完整一次性PG：现有指标Owner、方法Owner与Production EvalContract创建/冻结/真实readiness读取，再分别追加发布撤销/新指标修订/达到门过期时间，全部拒绝。未覆盖真实评测执行，套件/评测/门/发布数据为合成依赖；未跳过readiness或关闭约束。git diff --check通过。退出后的既有JDBC日志关闭流提示不影响退出码。

新增real-business-acceptance-matrix.md对应用户总进度与业务计划问题：正式八工作台、首条商品/订单→经营参谋主推内容计划→内部内容/媒体→评审续跑→总控/Wiki候选，缺真实来源不虚构，禁止SQL补状态/手工接refs；至少3个真实调度窗口含数据更新/重启恢复，业务效果成熟单独观察。所有真实业务项仍待执行。

边界：仅正式元数据读取，实际指标观察/QueryResult与受控Evidence绑定及D01生成尚待完成；公共Owner原评估套件/发布语义仍沿用，未执行真实评测。主库仍012、API未重载、无Provider/主库业务写入。下一波完整指标观察来源与D01固定请求/可信Insight，再工作者、正式三阶段宿主和配置、真实数据、首链、八场景及观察。不push，230 L0挂起，持续推进。
