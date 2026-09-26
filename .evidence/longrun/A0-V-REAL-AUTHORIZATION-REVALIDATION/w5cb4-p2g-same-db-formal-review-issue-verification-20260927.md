# W5CB4 P2g｜同一原内容候选的正式人工 ReviewIssue

- 基线 `m1@c8ab50ca`，先补第七增量文件级方案；只扩 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`。在同一正式 `a0v_105` 一次性库延续原 TaskRun、settled Artifact、成功生成 StepRun/checkpoint、冻结 READY 合同及正式通过的主体 EvalReport；先独立只读得到 exact 内容候选。
- 正式 `AipProductionContractStore.register_review_rule_revision` 注册内容人工 Rule，`create_review_issue` 使用候选 Artifact/hash、Report/revision/hash 与确定性 idempotency key 创建唯一 open ReviewIssue。相同请求重放返回同一 Issue；独立 SQL 核对唯一行的 exact Artifact/Report 和 open 状态；随后 `ContentReviewPendingReader.read_one` 返回 None，不再重复列出待办。未直接 INSERT Issue，也未由候选读取器写库。
- 专项 `1 passed, 6 deselected, 7 warnings`；内容、通用 EvalRunner 与邻近 PG 累计 `294 passed, 35 skipped, 7 warnings`；`git diff --check` 通过。纯后端隔离库路径，浏览器验收不适用。受控内容/Provider 响应及 Graph target/judge 不等于自然业务证据；未进行人类 ACCEPT/RETURN、review StepRun/TaskRun 终态、Host 当前安装锁、真实商品事实、网络 Provider 或生产 Issue 写入。
- 下一波：在同一原 Issue 上验证正式人类决策命令的 ACCEPT/RETURN、Host exact Receipt 与自动续跑边界；同时对合同撤销、旧 attempt、报告多义等做必要的同库 fail-closed 复审。仍不开放生产 GET/Worker，不读商城源、不重跑旧十二 Run／230 L0。
