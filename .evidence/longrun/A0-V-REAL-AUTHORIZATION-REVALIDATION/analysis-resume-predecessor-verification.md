# SC4-5b 原初始化回执作为恢复前置

2026-09-14；基线f34b5ab9；m1，不push。

原PREPARING/CONTINUE Receipt可作为resume_data前置，无需制造WAITING_DATA后继回执；原数据字段必须全部为空，Plan/Case/Occurrence/Profile/cutoff与请求精确对应。原WAITING_DATA Receipt兼容保留。

实际恢复Owner增加verified Run读取和WAITING_DATA/RUNNING检查，pendingRequirement必须是本请求；全部原Fulfillment/Readiness/Mapping/Hydration/Evidence/Checkpoint/质量检查保留。通用bootstrap恢复拒绝保持，没有真正执行Task步骤。

红测：真实初始化+实际数据请求后旧前置检查报RESUME_DATA prior authority drifted。绿测：原Receipt通过，实际Owner读取需求后因缺真实Fulfillment报fulfillment authority drifted，符合边界。六项纯合同测试覆盖合法初始化、错动作、伪填需求/检查点、假completed、换Plan。旧错误phase测试改用RUNNING，不能把新合法PREPARING继续断言为非法。

最终63 passed/7既有警告/29.53s（数据准备/分析Host/原数据恢复/包恢复合同）；AR2 1905/184/93错误数组全空；memory GREEN 1101/1084/2701；diff check通过。

局限：来源和安装等仍fixture；只验证前置和缺数据拒绝，不是成功续跑。主安装未部署，真实首链/八场景未完成。

下一SC4-5c：明确经营事实如何进入实际执行上下文，并接专用当前恢复守卫；初始化Context只能证明关联，不能直接当经营证据。后续还需安装内自动政策、实际补齐和三阶段业务输出。
