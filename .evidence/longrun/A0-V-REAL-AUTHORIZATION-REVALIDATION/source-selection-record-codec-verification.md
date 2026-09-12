# 来源选择记录严格编解码

2026-09-12，基线945ba918。新增pipeline_source_selection_store.py的build_selection_payload、selection_request_hash及decode_selection_row，当前仅编解码，不审批、不执行SQL、不调用源。记录固定schema/method版本，绑定完整草稿、读取规格、actor、selection/revision/previousHash与身份列；规范hash复用canonical_sha256。MappingReadSpec补严格构造校验，持久JSON回读不能绕过基础标识符、唯一列、主键及等值范围限制。

RED为缺新模块；初次关联80项通过。补充首条请求不依赖服务器随机ID，以及前序修订不接受bool；后者先1 failed/16 passed，再修正严格类型。最终记录codec/资产解释器/控制草稿共82 passed，3.74秒，7项既有警告。涵盖两修订往返、输入字典后改不影响冻结结果、身份列/actor/hash/requestHash/前序不一致拒绝、重新计算摘要后仍不接受额外授权字段或错误草稿/规格。首次请求hash中previousRef为null，不含新生成selectionId，支持下一步幂等复用。

AR2 ar2-7闭包1793/158/93，五类错误空，diff检查通过。原控制合同固定摘要仍不变。过期记录可解码用于审计，当前有效性与执行权限必须由Owner另行判断；不能凭SourceSelectionRecord对象自授通行。具体资产PII策略仍需Owner重新派生比对，codec不替代该检查。

下一波按source-selection-owner-service-plan.md继续当前权限组合、同事务CAS/幂等追加与拒绝测试。真实aos_meta_head尚未部署a0v_022，P01仍未读源、未启用。保持m1串行、不push，230 L0挂起。
