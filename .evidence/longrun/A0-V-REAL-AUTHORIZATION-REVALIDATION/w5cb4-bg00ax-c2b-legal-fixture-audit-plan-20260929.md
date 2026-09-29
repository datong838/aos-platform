# W5CB4 BG-00ax｜C2b 原链联合证明合法夹具审查

## Rules/方案

沿 231-1/5、D01 C2 总方案与 C2b1 现有负向事实，先读真实 `AnalysisContinuationOrigin`、数据恢复专用 Session、正式 Plan/selection、AIP Owner 的隔离 PG fixture。只有能在不读商城源、不重放旧 Run、不手工 run_definition、不 monkeypatch 生产 Owner 的条件下构成合法原 Task/Plan/Method/Eval/Query/Grant/approval，才写 C2b RED/最小实现。否则精确记录缺口并立即转 BG-00 独立配置/产品恢复项；当前库只读，Host/worker/Provider禁入。

## 文件级入口

- 复核 `test_ecommerce_analyst_d01_formal_ready_pg.py`、`test_analysis_snapshot_resume_chain_pg.py`、`ecommerce_analysis_data_resume.py`、`ecommerce_analyst_d01_atomic.py` 和现有 unit harness。
- 区分真 PG 原链恢复与 named snapshot fixture、mock 回调；统计能否获得唯一 AgentRun Owner Receipt。若缺合法 fulfillment/专用 Session，不新增绕行测试。
- 输出 verification/精确提交、下波最小独立代码项；不把 C2b1 负向或 mock unit test 说成 C2b 正向。
