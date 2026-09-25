# W5c9h｜原组行级语义证据谱系只读审计

## 现场与范围

承接方案 `m1@77263673`、W5c9g `m1@64a4dcf0`、AOS-000695。2026-09-26 CST 前检：`m1` 仅有两个已知测试 VM 配置文件未跟踪；真实 Docker 只有 `aos-a0v-recovery-pg` Up，18435 loopback；18181 纯 HTTP PID28077 存活，8080 无监听。没有启动 Worker、触发 attempt、读取商城源或修改真实 DB。原组精确聚合复用 W5c9b 强制 READ ONLY 结果：12 原 Run stalled、原组 Dataset Receipt 0、closure Receipt 0；全租户 Store Receipt 26 不能混同原组完成。此处未作新鲜原组 SQL 读回，时间差异保留。

## 事实谱系

| 层 | 实际路径 | 能证明 | 不能证明 |
| --- | --- | --- | --- |
| 源读取 | `pipeline_controlled_snapshot_group_ingress.py` 对 `read_selected_snapshot_group` 返回原始 `rows` 调用 `observed_rows_hash(rows)`，然后 `materialize_snapshot` 并保存 `outputRows` | 当次进程把自己读取的行计算成 manifest 的 `rowsHash`/`rowCount` | 事后存在一份独立、不可同错的原始行证明；连接器返回内容的业务真实性 |
| 保存输入 | `pipeline_snapshot_group_input_owner.py`、`pipeline_snapshot_group_saved_facts.py` 对原 `parent` envelope hash、保存 `outputRows` 数量、对象类型和部分字段作校验 | 已保存 envelope/输出行/成员关联的一致性 | 两处均只检查 `rowsHash` 格式，不用原始 `rows` 重算该 hash；`outputRows` 是映射后内容，不能当原始行独立副本 |
| 投影/Receipt | `pipeline_snapshot_group_projection_owner.py` 要求每 Run 的 Dataset Receipt 与已投影事件；`ec_ingress_dataset.finalize_saved_dataset` 从同一 parent/derived/projection 生成 build 行数与 Receipt | 同一保存/投影链完成后的内部结果 | 原始输入行语义或当前商城源真实性；原组当前没有这 12 个 Receipt |
| 独立产品 observation | `source_read_observation.py` 的 `verify_rows` 可对**提供的原始行**重算 hash；`source_read_observation_evidence.py` 写 product/quality observation | 该路径提供行数组时的内部一致性 | 与此 12-member snapshot group、相同原始读取事务、保存 manifest、原 Run 绑定；不能把另一产品观察证据挪作原组授权 |
| canonical sidecar | `a0v_097/098` 精确原 claim/input/member canonical 文本/哈希；W5c9f/g 恶意自洽 fixture 被写入 | 原始保存字节的见证 | `rowsHash`/`rowCount` 正确，或 ACK/Fulfillment/closure 权威 |

静态搜索 `pipeline_snapshot_group_canonical_witness_a0v_097`、`pipeline_snapshot_group_witness_backfill_a0v_098`：运行时 `aos_api/` 与 `scripts/` 无调用点，只有 migration/test。`a0v_007` Dataset Receipt 表保存 `payload`/`payload_hash`，没有另一个独立的原始 `rowsHash` 观测列。现有 row 验证能力不能凭空补出历史独立观测。即使将保存的 `outputRows` 与 manifest 对齐，也只能证明保存链内部一致性，不能恢复读源当刻未保存的原始 `rows`。

## 判定与停止线

对**原十二 Run**，目前 `NO_INDEPENDENT_ROW_PROOF`：没有已证明独立于原输入写入链、同源读取事务、精确成员/Run 绑定且可在消费侧复核的原始行证据。此结论不否认新读源可创建 observation，也不宣称历史真实行必错；它拒绝把自洽哈希提升为语义真实性。真实商城源禁止重读，本波不得做推测补证、迁真实库、接 sidecar 消费者、历史回填、ACK、Fulfillment 或 closure。Fleet/Owner/Host 全局权威缺口也仍独立存在。

下一波转向不依赖真实源或旧组授权的独立安全债，仍先方案。若将来取得合法独立原始行观测，必须另立隔离消费侧负例方案；不能把本 audit 当写授权。
