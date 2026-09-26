# W5cai｜A1 首链优先只读核验（2026-09-26）

方案 `94b04dea` 先行。本波无生产代码、真实业务库写入、商城源库读取、Runtime Host 重启或旧 attempt 重发。结论是**主线可转向业务产物编码；A1 真实自然运行尚未完成**。

1. 上位复习：231 §12/14 要求自然触发→真实产物→评审自动续跑→复盘；231-9 §2/7 要求一商品×有依据客群假设×场景，BG-01/02/03/04 串起来；产品方案 §8 的销售武器包要求适配/不适配、证据与禁止表述，不把商品 ACTIVE 写成有库存/利润。
2. 当前 AOS recovery PG `a0v_092` 只读统计：`org-org/dev-project` 有 26 个 Dataset Receipt，均标记 READY；其中商品 14、SKU 1、店铺 2，其余九类各 1。最晚 Receipt 为 2026-09-17 UTC，**仅证明历史已治理候选，不证明 9 月 26 日新鲜度或完整销售事实**。未查看商城源行。
3. 同租户 `automation_occurrence` 392：商品分析 event accepted 1、cancelled 116、pending 273；schedule cancelled 2；商品事件 origin 390、Case head 2。这些旧记录截至 2026-09-16 UTC，不能重放成当前自然成功。原 12 Run 未退休且不得用于新链授权。
4. 代码核查：`ecommerce_product_event_worker.py` 已具候选发现、消费、Occurrence dispatch；`ecommerce_scheduled_analysis_service.py` 已具周期分析 Owner 与来源组/批准/安装校验；`ecommerce_business_investigation_review_command.py` 已具四 Artifact exact 评审及内容 Handoff；内容 workflow 已存在。四组邻接专项新鲜执行 **24 passed**（7 个既有 warning），因此不为已存在的桥再造一套，不把单测当实际链成功。
5. 最早真实运行门是当前安装/有效数据截面/策略审批与运行资格的复验。可独立推进的核心代码是 BG-03/04：把单商品经营方法结果的有来源商品适配、客群假设、不适配、未知项和内容 Brief 接到既有 GrowthPlan/Review/Handoff，而非继续填补失败快照原始行。下一波须先逐文件核现有 DTO/Receiver/Owner，选最窄缺口，RED→最小实现→专项/累计/浏览器。
6. 非阻塞代办代查：原 12 Run 正式退休及旧入口撤权、其余商城表历史行证明、非首链旧 PG 风险文案、八页视觉边角。真实外部能力/费用/发送/发布仍受当前独立授权；未授权只挡对应动作，不挡无副作用实现。

本波没有前后端可验收变更；浏览器不可能据此确认 A1 自然成功，故不伪造浏览器 GREEN。没有重新计数 231 总进度。下一波转 BG-03 最小业务方法产物，仍以 A1 首链完整业务验收为终点。
