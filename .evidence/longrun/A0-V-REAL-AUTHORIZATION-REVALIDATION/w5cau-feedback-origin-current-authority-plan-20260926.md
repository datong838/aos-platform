# W5cau｜评审反馈原点的当前权限门（施工前方案）

## 上位约束与现场

- 231-5 §1/§4/§5/§7 要求内容评审后自动回流，但反馈执行须绑定同一有效安装代次；旧批准/旧 epoch 不可授权新实例。栖月汇产品方案 §9 的效果与经验对象须有真实来源，不得将内容生成等同销售效果。
- W5cat 只得到未构建、未签名候选源，当前 8080 未开放；不把它当成可安装实例。`ContentReviewHostService` 已在当前 Host 事务中生成 Review Receipt 和 durable feedback command；`BoundEcommerceGrowthFeedbackPort.claim` 尚未检查该命令是否来自当前 Review Receipt/Dispatch/Runtime。四个目标执行者仍未接线。

## 本波文件级清单与边界

1. 修改 `services/aos-api/aos_api/ecommerce_growth_feedback_port.py`：新增供正式 Worker 使用的 `claim_current` 原点门。它在底层 claim 前，从持久 feedback command 的原始 Review Receipt Ref 精确定位唯一 `ecommerce_growth_content_review` runtime Receipt，校验 response 中的 Review/Artifact/Task/Brief/decision；再按宿主锁序检查当前 Dispatch group 和 Runtime binding 全组可执行、版本/epoch/安装代次与该 Receipt 一致。任何缺失/多义/旧代/未知结果 fail closed；先返回阻断，不增 attempt，不执行目标。原 `claim` 留作已存在的低层 AR2-7C 隔离协议测试，不作为生产 Worker 入口；下一波 Worker 只能依赖 `claim_current`，且目标写前须再次复核 fence。
2. 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_feedback_current_origin.py`：RED→GREEN 覆盖唯一当前原点、缺失/多义、旧代/禁入、Review 内容漂移，确认无 claim/目标调用。
3. 仅跑专项与邻近回归；复核方案/代码与兼容性。无数据库迁移、无 Provider/商城源调用、无自动目标写入、无手工业务重发。旧命令不可借此变为可执行。

## 退出/停止

- 验证文件须注明单元/PG/浏览器真实证据的差别，给出下一波 `daily_review` 真实接收端与其 Receipt 的施工入口；未达到本波证据前不宣称反馈续跑完成。
- 当前实例没有可信安装或 Registry/8080 不可达时，只阻断活体验收，继续可独立研发；如出现未知目标副作用，冻结而不重发。
