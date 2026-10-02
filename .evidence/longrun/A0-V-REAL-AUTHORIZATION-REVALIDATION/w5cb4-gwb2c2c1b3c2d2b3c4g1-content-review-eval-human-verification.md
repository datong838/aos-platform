# d2b3c4g1｜原阶段内容评审 Eval/人工 Owner 读者验证

## 基线与范围

- `aos-platform/m1@24b5eb76`；本波仅修改 `ContentReviewHostService.revalidate` 的 `accepted-stage-v1` 分支，复用已存在的内容 Issue/Eval 与独立 reviewer 读者。原 Issue 路径、`execute`、`verify_receipt` 和运行 Host 均保持禁入。
- 当前真实数据库只读；专项测试使用可销毁 PG。测试 seam 仅证明读者调用顺序与失败封闭，不能充当正式原 Review Receipt 或内容 Issue 生产者。

## RED、GREEN 与相邻回归

1. RED：`test_ecommerce_content_review_authority_feedback.py::test_accepted_stage_review_execution_stays_closed_before_database_effects` 增加两个读者调用断言后，旧实现 `1 failed, 11 deselected`，退出码 1；失败点为受理原 Stage 后未读取内容 Issue/人工 reviewer。
2. GREEN：增加两行生产调用及缺 Issue 负例，定向测试 `1 passed`，退出码 0。
3. 可销毁 PG 相邻测试：`test_ecommerce_review_task_brief_authority_pg.py`、`test_ecommerce_content_review_authority_feedback.py`、`test_ecommerce_content_generate_handoff_lineage.py` 共 `44 passed, 7 warnings`，退出码 0。连接参数来自当前签名预览 preflight，未连接当前真实库进行测试写入。
4. `py_compile` 与 `git diff --check` 退出码 0。

## 运行与浏览器回读

- API LaunchAgent `com.aos.a0v-api-daily0900` 重载后 PID 55654，8080 `health`/`ready`、8434 页面均 HTTP 200；18181 无监听。此处是 API 重载验证，**不是** PG→API→Web 完整重启门。
- 内置浏览器只读观察 `http://127.0.0.1:8434/aip/skill-publish`：当前 `org-org/dev-project`，37 项仅评测、0 正式发布；首批发布列表继续列出正式发布决定、业务逻辑版本、运行绑定/策略三类阻断，发布动作不可用。截图已由浏览器工具在本轮捕获；本波未将工具截图写成仓库文件。

## 方案一致性与剩余风险

- 调用顺序与计划一致：可读内容 Artifact/原 Stage 与 Review Receipt/v3 Brief → 内容 Issue/Eval → 独立人工 reviewer → GrowthPlan hash → `Host is not wired`。新增负例证缺内容 Issue 会先于 reviewer 失败；无数据库副作用。
- 原 Analysis/G2 Skill Eval、持久原 Review Receipt 联合正向、正式内容 Eval/Issue 和真实人工事件、执行/反馈回执、E17 外部身份/八配置/Host assignment 均未完成。当前实例仍不得启 Host/worker/Provider，不得将浏览器 200 或局部测试当作自然首链成功。
