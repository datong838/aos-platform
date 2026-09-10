# 三个真实文本评测样本执行方案

新增 `/Users/ddt/work/projects/ai_agent/aos-platform/scripts/a0v_exact_text_live_eval.py`，固定隔离库、正租户、现有 Provider@1 和 Network@1。Task/Lease 为 A0V-EXACT-TEXT-LIVE-EVAL；用户已明确授权开发调用费用。

固定三个合成公开样本：精确中文指令、给定来源 ID、销量未知标记。只作为模型能力样本，不是租户业务数据。每个样本冻结 request hash，独立原子排他创建 attempt 文件，提交前 fsync；已存在的完成记录仅回读，未完成记录拒绝重发。记录精确 Provider/Network 引用、合同 hash、模型与 token/延时结果，不记录响应、密钥或 headers。无 DB mutation，不发布 Eval Gate/健康观察，不把样本通过冒充业务就绪。

沿用当前受管文本 timeout；媒体延长等待另在对应 Provider 的正式策略修订中实施。本次最多三次真实调用，无隐式重试。执行前验证 journal 排他/重放/漂移，执行后再次运行证明无新增调用。
