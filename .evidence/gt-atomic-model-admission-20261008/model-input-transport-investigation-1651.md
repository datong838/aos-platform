# Model 实际请求边界调查与下一实现门

Rules：231、原 atomic Task 的完整退出条件、m1 单写、正式库只读及 Provider 禁入。修改仅本 Task evidence 目录；没有修改生产代码或旧 Skill 路径。

基线 f7a5c7dfa / AOS-001651。候选一为可信事务结束协议；上一原生 callback 反例已证明单 PRE_COMMIT 检查不能保证实际完成截止。候选二为完整 Model 输入/Quota/请求接线，沿已登记计划继续，当前选择候选二。

本次 r1 在私有 passfile stat 阶段失败，尚未建立数据库连接。旧 `/tmp` 凭据已不存在，未改认证、创建凭据、重放旧审批或调用 Provider。r2 改为明确独立的纯编码调查，保留原失败脚本；它读取旧只读快照，不能替代当前原表回读。

本次原代码与当前 HTTPX 编码验证：两个历史父申请、四个 ASCII/Unicode 样本。原 Quota payload 的 canonical hash 重新验证；历史 context 8000、输入上限 8000、输出上限 2000，保守 physical obligation 10000。实际 chat JSON 包含 provider model id、messages、max_tokens；Artifact 值的 canonical hash 与实际 UTF8 request body hash 均不同。UTF8 byte length 不等于 token count，未认证 tokenizer。

旧 LLMAdapter 的 invoker 调用无 max_output_tokens 关键字。原纯 payload assembler 缺省不输出 max_tokens，并且接受高于历史 Quota 的数值。原 invoker AST 没有直接 context_window/max_input_tokens 属性读取。这些证明不能将原编码器直接当作完整 Model envelope；不单凭纯编码结果宣称整个 invoker 会违规 dispatch。旧 Skill 原有行为不在本次变更范围。

当前完整 Model/input/transport 仍 RED，未发主 Task Delivery。下一实现必须由 Model 专用 Owner 在原申请、current Model/Quota exact ref、原输入字节与 Target/Judge 依赖上产生固定请求 envelope；预算占用与实际 token/context、输出硬限制、实际编码 SHA 分别绑定。可选择经过审批的精确 tokenizer，或有正式依据的保守上界；不能把字符数、JSON 长度、调用者声明的 tokens 当真实上界。新的 transport 入口先登记精确文件与 Lease，再 RED 与最小实现。不得放开旧 Runner/正式 Provider，也不能用 envelope 子波通过来替代 Source 终态与完整联合准入。

自审：r2 返回 0 仅表示调查断言成立，不表示 Model 准入通过；原表即时 Model head/审批未复核；无真实请求、tokenizer、DB 查询或外部效果。实际输出 cap 接线测试、可信输入 producer、Source 完成时限、唯一 Intent 与结算仍未完成。
