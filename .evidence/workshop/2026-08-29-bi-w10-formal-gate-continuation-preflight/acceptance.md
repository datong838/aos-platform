# BI-W10 正式门连续执行预检验收

## 范围

- 复核 BI-W10-02～06 与 BI-W11-01～05 的正式 DAG、既有预检 Receipt 和当前完成证据。
- 修复 `scripts/data/export_source_readiness_evidence.py` 在 macOS 系统旧 Python 下无法导入 AOS API 的运行时自洽缺口。
- 只读回收 `org-org/dev-project` 当前 SourceReadiness；不手工运行 Pipeline、不重放 DLQ、不创建 Case/Run、不调用 Provider、不修改真实业务数据。

## 当前事实

- Git：`m1@e1389c9d`（修复前基线）。
- API runtime：PID `17608`，唯一 `127.0.0.1:8080` owner，项目 Python 运行。
- SourceReadiness 截点：`2026-08-28T18:56:02.579496Z`，`10/12`；P01 新自然 run `scr-af11cebe1f34469b` 成功，P07/P08 仍保留各自上一自然失败事实。
- BI-W11 确定性基线复跑：`1222 passed / 0 failed`；历史 `1185/1185` 未倒退。

## 修复与验证

- 脚本在导入 `aos_api` 前检查 Python `>=3.10`；旧解释器自动切到仓内 `services/aos-api/.venv/bin/python`，候选不存在或自身仍不兼容时以稳定 code 失败关闭。
- SourceReadiness evidence 专项：`4/4 GREEN`。
- `/usr/bin/python3 scripts/data/export_source_readiness_evidence.py --help`：自动切换并成功输出帮助。
- ecommerce/SourceReadiness 累计：`1222/1222 GREEN`。
- `compileall`、`git diff --check`：GREEN。

## 结论

结果为 `BI_W10_FORMAL_GATE_CONTINUATION_PREFLIGHT_GREEN_SOURCE_READINESS_10_OF_12_NATURAL_P07_P08_PENDING_NO_EXTERNAL_EFFECT_NO_RELEASE`。本结果只关闭证据采集工具和正式执行矩阵缺口，不提前完成 BI-W10-02，也不改变发布决定。
