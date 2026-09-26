# W5CB4 P2f-b 第 4/4 步｜内容预审权威受控安装方案（编码前）

## 复习、现状与目标

- 上位 231-5 §1/4/5、231-9 BG-04、栖月汇产品方案及本波 P2f 方案均要求：内容 Artifact 的结构/来源预审合同来自可追溯的正式发布链，人类 exact Review 才作业务判断；不得从模型生成自评或 C06 Skill 治理评估借用授权。
- m1 `b771dc66` 已有只读唯一当前权威读取器与新 Plan exact gate；一次性隔离 PG 已证明 Graph→治理/主体 Suite→Gate/Publication→冻结 READY 合同的 API 可行。当前实例此前只读为 `a0v_092`，代码迁移至 `a0v_105`，内容主体合同 0；未证明当前实例可安装。首链 Worker、Provider、外部发布仍不得启。
- 目标先实现**可预检、可分步恢复、不可未知重发**的受控 bootstrap，不以一次性 PG 结果宣称当前实例成功。当前实例迁移与注册必须单独有精确读回、作用域、单写/停 Worker 和失败冻结证据。

## 文件级清单与最小实现顺序

1. 只读复核 `aip_logic_graph_store.py`、`aip_eval_pack_registry.py`、`aip_eval_runner.py`、`aip_release_publication_service.py`、`aip_production_contract_store.py` 的公开 API、幂等键、提交边界和当前库 schema。复核第 2/4 步正式 API 测试构造，记录各步 exact 输入及读回证据；任何 API 的未知提交都停在该步，不进入后续，不靠重调猜结果。
2. 新建 `services/aos-api/aos_api/ecommerce_content_pre_review_bootstrap.py`：提供只读 `preflight(scope, connect_factory)`，核租户、schema/迁移、现存当前候选唯一性和旧定义碰撞，不读商城源；提供显式、分阶段 `install`，固定 Graph/Suite/Contract 规格与稳定幂等键，复用上述正式 API，逐步独立读回。预检拒绝时不得写；写阶段任一步未获确证即返回冻结状态/抛出需人工对账错误，绝不自动重试/重发。不得修改全局合同 readiness 或旧 Plan。
3. `services/aos-api/tests/extension_runtime/test_ecommerce_content_pre_review_bootstrap.py` 先 RED：空隔离库正向安装与二次只读复核；错租户、已有非本包合同、多当前合同、Graph/Suite/hash 漂移、撤销/过期、未知提交和迁移不足均失败关闭。可复用第 2/4 步一次性 PG fixture，不连接当前业务库；`dev-org/dev-project` 只作为零 canary。
4. 专项→内容邻近累计→隔离 PG 状态/租户读回→方案代码一致性复审→verification 文件→精确 m1 commit→AOS/Prime 项目上下文。无 UI 改动不作浏览器验收；若产生页面再实测。

## 安装边界与退出条件

- 安装不可在生产库默默迁移或开启 Worker。应有显式目标 DB 与 scope、schema exact head、运行端口/Worker 唯一性预检；现有配置和内容合同非空/多义一律停，先只读对账。每个正式 API 有独立提交，因此未知结果必须冻结边界，不能把“幂等键相同”当成未知重发许可。
- 本 4/4 步只有受控 bootstrap 在隔离 PG 完整正反证明、当前实例读回与安装决策均完成，才可称 P2f-b 完成。否则 verification 标记部分代码门与实际缺口。P2g 才实现真实已结算 Artifact 的主体 Eval、待办、人工决定与 TaskRun/反馈续跑；不得因安装门拖延与之不冲突的离线编码准备。
