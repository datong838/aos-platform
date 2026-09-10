# A0-V 精确文本评测施工卡

目标：真实模型评测不能以非空文本代替指令遵循。复用现有受限探针，在调用前冻结预期文本；响应仅在进程内比较，输出继续只含 metadata。

修改文件：`services/aos-api/aos_api/aip_r1_bootstrap_probe.py`、`services/aos-api/tests/aip/test_aip_r1_bootstrap_probe.py`。新增 `exact_text` 行为及 repr 隐藏的 expected_text；只有该行为允许且必须提供非空预期文本。比较仅忽略首尾空白，不吞掉额外解释、来源错误或虚构字段。image/video 不支持该合同，必须在 Secret/transport 前拒绝。

固定后续真实样本：仅回复指定中文词；根据公开的虚构商品材料输出给定来源 ID；未提供销量时输出缺失标记。这些是明确标注的模型评测样本，不写入租户业务表，不冒充栖月汇数据。每个样本 independently receipt-first、一次尝试；不在本代码切片调用 Provider。

验证：先新增失败测试，覆盖精确成功、额外解释失败、预期缺失/误绑定拒绝、非文本拒绝、metadata 不含预期或响应；回归默认 non_empty/refusal 和 A0-V 健康行为。失败只返回稳定错误码，不包含正文。本切片沿用 m1 A0-V Lease，无 DB mutation，不 push。
