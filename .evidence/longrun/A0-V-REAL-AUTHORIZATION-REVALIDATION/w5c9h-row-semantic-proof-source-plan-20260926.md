# W5c9h｜见证消费前独立行级语义证据来源审计

## 上位边界

承接 W5c9g `m1@64a4dcf0`/AOS-000695：`a0v_098` 可在隔离 PG 为哈希自洽但错误 rowCount/rowsHash 的原输入插入 canonical sidecar；应用当前没有 sidecar 消费者。必须防止未来把“原字节存在”解释为行级真实性、Fulfillment/ACK/Store/Link 或原组 closure。禁止读取真实商城源，真库未迁 096/097/098，12 原 Run 仍无 closure/Fleet/Owner 权威。

## 本波只读文件级清单

- 审 `a0v_007` Dataset Receipt、`source_read_observation.py` 的 `verify_rows`、`pipeline_snapshot_group_input` manifest 与现有 Receipt/Projection 写路径，列清哪种事实只是自报、哪种由独立实际行读回证明；不读取真实 row/payload。
- 只新增 plan、audit、verification；不接侧表消费者、不启动 Worker/ACK、不修改真库或生产代码。若 `DatasetReceipt` 仅在本地派生且无原行 hash/count 独立来源，明确 `NO_INDEPENDENT_ROW_PROOF`，不能编一个布尔字段假装权威。
- 静态搜索 sidecar/function 引用与当前原组 DatasetReceipt 计数（使用 W5c9b 已证只读聚合；若需新鲜确认，仅强制 READ ONLY 精确组计数），输出 0/非 0、来源/消费路径，不输出商城源数据或凭据。

## 九步

1. 复习 231、W5c8q/r、W5c9f/g 与原组 no-authority。
2. 本方案先提交。
3. 当前 PG/18181/8080 与精确原组只读前检。
4. 静态证据谱系与消费侧授权缺口审计；未知即停止推断。
5. 如无需代码，本波专项为引用/SQL 路径复核，历史测试不冒充本波实测。
6. 方案/代码一致性复审，明确 canonical/行级/Receipt/Fleet 分层。
7. 8080 业务浏览器离线，不填业务 GREEN。
8. audit/verification、m1、D-waves/AOS CAS/Prime。
9. 自动下一波：若独立行证据来源不存在，转向可独立完成的安全债；真实 ACK/closure 持续冻结。若来源存在，另立隔离消费侧负例方案。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push、不读商城源。
