# W5cai｜A1 首链核心优先与现有数据复用方案（2026-09-26）

## 上位与目标

依 231 §12/14、231-9 §2/7、栖月汇双侧增长产品方案，交付目标是**一件真实商品×一项有证据的客群假设×一个场景**，由合法数据更新/已批准周期自然形成 Occurrence→Case/Run，再经有来源建议、exact 评审、内容任务、真实能力产物、人工评审续跑与 EffectReview/Wiki 候选。已有可信主要数据只要足够首链就复用，不把原 12 Run 全表补齐、历史原始行证明或旧测试措辞列为首链前置。旧失败组的正式退休已在 W5cah 记录为独立待办，禁止重发、禁止冒充业务成功。

## 文件级范围和执行顺序

1. **事实门/只读**：从当前 AOS 权威的已治理 Dataset/Store Receipt 与来源水位读取商品/店铺可用性、同租户和安装代际；不连接商城 SSH/源库，不读取源行。对现有商品事件→Occurrence→Case/Run，以及 review→handoff→content→回流的文件/测试做一次短清单，分为“已实现可复用、真实配置缺、代码缺、外部门缺”。重点文件及前 hash：`services/aos-api/aos_api/ecommerce_product_event_worker.py` `5162d3fc`、`ecommerce_product_event_discovery.py` `e66dd6a0`、`ecommerce_scheduled_analysis_service.py` `a53917d7`、`bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_review_command.py` `17812042`、`ecommerce_content_campaign_workflow.py` `b2fac831`。现有专项测试为 `services/aos-api/tests/extension_runtime/test_product_event_worker.py`、`test_product_event_discovery_pg.py`、`services/aos-api/tests/test_ecommerce_scheduled_analysis_service.py`、`test_ecommerce_business_investigation_review_command.py`、`test_ecommerce_content_campaign_workflow.py`。
2. **选择最早阻塞动作**：以 A1-02 到 A1-06 的一次真实业务动作序列为单位定位第一个缺口，不为边缘事项造新通用框架。如果现有数据可用于分析但无新更新，沿 231-9 已批准经营周期分析当前截面；没有有效周期/权限则仅完成代码与隔离验证，不手工制造事件。任何用户操作仍经产品入口，不用开发脚本冒充。
3. **最小改动/专项**：找到可证伪的代码缺口后，先在上述邻接测试或对应产品入口测试 RED，再仅修改对应 Owner 文件；若缺的是实时授权/配置而不是代码，不写猜测性补丁。保留幂等 Receipt、租户、exact refs、预算/审批、未知结果冻结。不修改失败组或商城原始数据。
4. **累计/浏览器/复审**：运行受影响模块及相邻回归，编译/类型/静态合同，浏览器只读或获准内部动作验收；如未形成真实自然触发和产物，明确记为 CODE_ONLY/OPERATIONAL_BLOCKED，不能称 A1 完成。校验产品方案的一商品/人群/场景和 231 的 A1-02…06 与代码一致。
5. **证据/上下文**：verification、AOS 上下文、D-waves 代办代查及 Prime 受管记忆更新后提交 m1；下一波直攻剩余首链最早阻塞动作，不回到旧快照边角。无 push、230 L0 挂起、`dev-org` 零 canary。

## 非阻塞代办代查

- 原 12 Run 正式退休及旧定义最终撤权：保留安全方案，重新行动必须 fresh DB/本机排他核验；不阻止 A1 无副作用编码。
- 尚未证明影响一商品首链的其余商城表、逐行历史来源、非当前自然触发路径的旧 PG 测试措辞、八页视觉边角：只登记，不占当前主线。
- 真实能力调用、费用、发送/发布/改价等仍需各自当前授权；这些门只阻止相应真实副作用，不阻止前置代码与隔离测试。

停止条件：现有数据来源或同租户水位不可信、跨租户/重复副作用风险、代码与 Owner 合同冲突、真实动作授权缺失时，只停对应动作；不得用 mock/旧 Receipt 补成功，也不扩大为全项目停工。
