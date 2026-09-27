# W5CB4 当前定义发布 intent 前置子波计划（2026-09-27，编码前）

## 目标与上位边界

- 承接 `7c377876` 的 1.11.0 来源 adapter；本子波只建设**只读的当前库定义行分类器**和独立测试，不执行 53 行发布。231 A0-V/BG-00 与产品方案 9.3 的版本/证据/未 ready 失败关闭为上位门。
- 现有 10 Capability→6 Agent→37 Skill 的 Owner 每行独立提交，不能假装跨 53 行事务。若存在部分行或未知先前写入，本波必须给出 `FREEZE`，不能重发或借旧 1.2.0 来源拼齐。

## 文件级清单、测试与下一门

1. 新增 `services/aos-api/aos_api/aip_current_definition_publication_gate.py`：纯函数接受三表只读行投影，核 6/37/10 目标 ID、source revision、revision=1、hash 非空，分类 `EMPTY`、`COMPLETE`、`FREEZE_PARTIAL_OR_CONFLICT`；仅 `EMPTY` 可进入未来唯一 intent 写流程，`COMPLETE` 只能只读报告，不作为二次写许可。
2. 新增 `services/aos-api/tests/aip/test_aip_current_definition_publication_gate.py`：空、精确全量、缺行、异源、同键重复、错版本/hash 等专项；不得用 current DB 做测试写入。
3. 用当前新库只读 SQL 做目标分类核验，并复查 8080/8434 安全预览；无新页面，此波浏览器只读查旧禁入状态，不要求本轮前端热重载。
4. verification 明确当前库未写、不得重试边界、后续唯一 intent/精确连接工厂/签名同边界核验及隔离 PG 测试；plan+code+tests+verification 同一 m1 提交，随后自动进入唯一 intent 发布执行子波。

停止：当前库若非 EMPTY，先冻结现场，不运行发布器。原 12 Run、商城源、Runtime Host/worker、Provider、业务配置与其他分支均不碰。
