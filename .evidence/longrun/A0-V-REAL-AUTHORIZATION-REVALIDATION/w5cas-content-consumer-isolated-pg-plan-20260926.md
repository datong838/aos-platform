# W5cas｜隔离 PG 消费/产物真链回归与新包前置门（开码前方案）

上位：231 A1、231-5 内容产物/费用/恢复与两批自然验收、231-6 AR2-7D 内容 Host、栖月汇双侧增长产品方案；W5car verification。基线 m1 `85315f44`。本波不读商城源，不开启 Provider，不碰旧 12 Run；只修阻碍 Consumer/Usage/Artifact 真实事务回读的**测试基线**。签名包版本与安装切换单列 W5cat，不能拿测试绿替代真实安装授权。

## 串行第 1～6 步与文件级清单

1. 复查原 AIP-1 `aip_artifact`、AIP-4 `aip_lineage_event` 及其后续迁移、预算/Consumer/Usage/状态 Owner；记录空 PG 的公共基线缺失与所需字段/约束。保留现有临时隔离 PG 127.0.0.1:18432，绝不连真实业务库。
2. 在 `services/aos-api/tests/aip/` 增测试专用 fixture helper，按原迁移最新结构在每例随机 schema 建必需的 lineage/artifact 表和权限，拒绝从不存在的 `public` 复制。只改 `test_a0v_content_result_consumer_pg.py` 与 `test_a0v_content_usage_pg.py` 的 fixture 调用；产品代码不因测试环境降门。先跑旧 9 项 RED，后 GREEN。
3. 补 `CurrentContentStatusReader` 的隔离 PG 端到端：原 Worker mock Provider 返回测量值→Journal→原 Consumer 原子 Usage/Artifact/Budget→新独立 Reader `COMPLETED`/`COST_PENDING`；注入中途失败回滚、缺 Artifact 拒绝、dev-org 零 canary；原状态测试文件 `test_ecommerce_content_execution_composition.py`，必要时新增 `test_ecommerce_content_execution_status_pg.py`。
4. 累计 W5car 78 项与旧 Consumer/Usage 9 项，编译/diff check。只在真实隔离 PG SQL 完整成功时写 GREEN；无 UI/路由改动浏览器 N/A。
5. 复审与 231-5/6 一致：可读正文、事实来源、两类 Usage、预算不超上界、UNKNOWN 无重发；如果发现产品代码缺口，仅在本方案增补精确文件清单后最小修复，不为测试伪造授权。
6. 落 verification、m1 精确提交、同步 D-waves/AOS 与 Prime 记忆，自动进入 W5cat：新签名包版本、安全安装迁移和当前 scoped authority canary；只在全门通过后考虑一次自然内容外呼。

停止条件：PG 基线若牵出不可安全复现的公共迁移，不死磕历史全库；记录明确缺口，转 W5cat 中无外呼的包合同开发。任何已提交/UNKNOWN Provider 结果绝不重发。开发默认关、dev-org 只零 canary、230 L0 挂起。
