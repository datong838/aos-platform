# O4 b70/b71 冻结资料独立复核

一次实际 agnes-2.5-flash 调用，transport returncode=0，result verdict=PASS；三个 claim 均 supported。消费成功 CONSUMED_MATERIAL_REVIEW，execution_authorized=false。

材料范围为冻结摘录和原输出，不声称模型另读完整源代码。支持 b70 两项真实 RED、b71 test-only 两顺序候选及 b72 幂等/回滚/正式写者合同路线。自然首链、当前实例权限、其他来源、正式迁移、新 thread 实际提醒到达和全天候 O4 效果仍未通过。

消费第一次 CLI 缺 --request 被参数解析拒绝；补齐 request 后仅本地消费，未再次调用模型。

Transport event counts: {"session": 1, "agent_start": 1, "turn_start": 1, "message_start": 2, "message_end": 2, "message_update": 944, "turn_end": 1, "agent_end": 1}
