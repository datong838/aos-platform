# Y5f4-Q 受控源失败分类与恢复资格方案

日期：2026-09-17
基线：m1 `e0d7b776`

## Rules 与实证前提

- 方案先行，先复核 P 波真实失败、连接器、selected reader、PipelineEngine 与现有脱敏测试，再改代码。
- m1 单写、最小修改、不 push、230 L0 挂起；不触碰用户进度文档、package 文件或其他脏文件。
- `scr-09fc7164153f4d7d`、其 source claim 和失败事实不可变；本波不启用 schedule、不执行 SSH/JDBC 探测、不产生第二次源调用。
- 错误正文继续只允许通用文案；稳定错误码只能来自闭合白名单，不能携带 host、port、user、database、password、SQL、源数据或原异常文本。

## 问题

真实 Cron 已进入 `ControlledSnapshotIngress.prepare` 并持久化一次 source claim。JDBC 日志显示 SSH tunnel 开始建立但未出现 ready；约 10 秒后失败。`JdbcConnectorRuntime` 已能把 SSH stderr 映射为闭合诊断码，`PipelineEngine` 也能把原始连接器异常映射为安全业务码，但中间的 `read_selected_snapshot` 捕获全部异常并统一改写为普通 `ValueError('SELECTED_SNAPSHOT_READ_FAILED')`，导致上层只持久化 `PIPELINE_EXECUTOR_FAILED`。

该丢失使系统无法基于 Receipt 判断是传输失败、MySQL 连接失败还是输入拒绝，开发者只能看进程日志推断，不满足无需手工接线的恢复要求。

## 设计

1. `jdbc_connector_runtime.py` 提供纯函数 `connector_failure_code(exception)`：仅识别本模块生成的两种 SSH 前缀及现有 pymysql `OperationalError` 数字码，返回既有安全码或 `None`。原 `_classify_ssh_stderr` 与通用正文不变。
2. `pipeline_selected_snapshot.py` 增加 `SelectedSnapshotReadError`。对所有失败仍以固定字符串 `SELECTED_SNAPSHOT_READ_FAILED` 对外显示；若直接捕获的连接器异常可分类，只把白名单 `code` 放入异常属性。来源窗口、scope、revision、行结构、截断等业务拒绝统一保留 `SELECTED_SNAPSHOT_READ_FAILED`。
3. `phase5_pipeline_engine.py` 的 `_safe_error_code` 优先读取 exact `SelectedSnapshotReadError.code`，随后复用 `connector_failure_code` 处理未经过 selected reader 的连接器异常，最后保持 `PIPELINE_EXECUTOR_FAILED`。`_safe_error` 始终返回通用正文。
4. 不新增数据库表或迁移；下一次真实运行会沿现有 `meta_schedule_run.error_code` 持久化安全码。历史失败不回填、不猜测。
5. 恢复资格仍由后续波决定：当前 run 无 durable ingress 且 source call 已用完，不能走 saved-input recovery；只有当前 SSH/JDBC 健康、后继 authority/policy 和新 Cron slot 全部通过，才允许新 run。

## 测试与退出条件

- selected reader：SSH 未就绪、SSH auth/timeout、MySQL connect 等只保留固定正文和白名单属性；秘密字符串不出现在 `str/repr/__cause__`。
- PipelineEngine：嵌套 selected reader 错误得到精确安全码；普通 ValueError、伪造 code、任意含 `diagnostic=` 文本仍为 generic。
- JDBC：原 stderr 分类与 tunnel cleanup 回归。
- controlled ingress / Cron 原回归、Python compile、diff check 通过；AR2 扫描只记录既有漂移。
- schedule 保持 disabled，P run/claim/ingress/occurrence/Case/Run 计数不漂移。

## 文件与 preHash

- `services/aos-api/aos_api/jdbc_connector_runtime.py` — `81ad6c6271abcb4f5dc79d4e91ad7e975f8b4be95202f4eec41fdbd4233be7a7`
- `services/aos-api/aos_api/pipeline_selected_snapshot.py` — `19c589854cdda2ceb2f97d355facec07d1c240050e010da391e6d88661ac1e36`
- `services/aos-api/aos_api/phase5_pipeline_engine.py` — `46c0a737d9af90693b23d52190a62d89a911f4106823b7064cd4520e185866b5`
- `services/aos-api/tests/test_jdbc_connector_runtime.py` — `996edcede6704738effeba0874ff8c73c3d793e0d6aa693427e42ec9429c98a8`
- `services/aos-api/tests/test_pipeline_selected_snapshot.py` — `6b763b4ba07dfddf290fd2ad0bff90116b2bf6d994e6b81df39fffa4709da5a3`
- `services/aos-api/tests/test_ec_pipeline_honesty.py` — `c763ef7d954878ae76ff07e0c5ef4ec34e819cc1526a580cdfb47743c8e3404e`
