# W5c4s 失败自然定义正式停用验证（2026-09-25）

结论：**定义停用 GREEN；原失败组/12 Run 未收敛，未退休，A0-V/BG-00 仍未 GREEN。** 方案 `18624fe3`；最小脚本与专项 `09011b62`，审计连续性补强 `30f0f919`。没有人工 `run_definition`、旧 generation 重发、商城源行读取或 push。

## 九步闭环

1. 上位方案：复核 231 A0-V→A1、231-9 BG-00→BG-01/02，以及 W5c4r 失败验证 `0c9a8c42`。原 Owner 代码规定 `retire` 只能在 disabled 且无运行中/未知 Run 后执行；本波只做 `disable` 防止下个 Cron。
2. 文件级范围：本方案、`scripts/a0v_w5c4s_disable_failed_definition.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c4s_disable_failed_definition.py`、本验证。其他业务代码、Host 与 worker 未改。
3. 最小控制动作：20:23 UTC 只读 `W5C4S_DISABLE_PREFLIGHT_GREEN`，精确 rev3/hash、唯一 cron group/failed PermissionError attempt、12 running Run、Store26/live link0/pending0/canary0、Host 已停、18181 原 worker 唯一、key0，且原 `service.read` 权限通过。固定 key `a0v-w5c4s-disable-after-natural-failure-20260925-v1` 的 0600 intent 在调用前独占落盘；仅一次原 `SnapshotScheduleService.transition(intent='disable', expected_ref=rev3)` 返回 rev4 `disabled`、hash `sha256:d3c28bf5ea17e299fe598b662da238aeecbb3f0f4227c96da3b44a8f4f49c32d`。私有 result 0600 留存。
4. 专项：先 RED（脚本缺失），后 7 passed；覆盖第二 attempt、副作用/canary、Host/定义/member 漂移、已用 key、只调用一次以及 unknown 留 intent 不重试。`py_compile`、`git diff --check` 均通过。加强后的只读 `audit` 再次 `W5C4S_DEFINITION_DISABLED_GREEN`。
5. 累计回归：隔离 `aos-dev-pg` 上 W5c3/W5c4r/W5c4s 与定义 PostgreSQL 合同合计 **90 passed、7 warnings**；未使用共享测试数据库，测试后容器恢复 stopped。
6. 浏览器验收：临时 AOS 前端 `127.0.0.1:5174/data/schedules`（默认 5173 被另一项目占用）可见 org-org/dev-project 与 12 条单路计划，但页面不展示可独立确认的 enabled/disabled 位；整组配置/安装实例入口仍不完整，且页面存在 1 项待同步写操作。未冲刷或点击保存/运行。记 **BROWSER_PARTIAL**，以原 Owner 与数据库核控制状态；前端已关闭。
7. 方案/代码一致性：独立只读 DB 核 head rev4 disabled、唯一 key rev4 的 `previous_hash=rev3 hash` 且新 hash 与 result 一致、12 current member 均 rev4；原 group 12 schedule enabled0、12 Run 仍 running。Store Receipt 仍26（本次增量0）、link0、pending0、canary0；原 attempt failed 与 Host stopped 未被重新写成成功。`PermissionError` 与 Host `HealthObservationStale` 的确切因果/抛出点尚未定位，不能仅凭时间相近作结论；下一波继续只读诊断。
8. 证据与上下文：本验证提交后，以 expected revision CAS 更新 `docs/palantier/AOS项目开发上下文`，经受管 sync 推送 Prime 三条长记忆并独立回读；只精确暂存相关受管文件，保护 docs 其他 dirty 改动。
9. 下一波 W5c4t：复核 disabled rev4/12 running Run/零副作用，先定义正式 Run 收敛与退休的 Owner 路径，并定位 `PermissionError`、Host health stale 的具体门禁。未解决前不得重启 Host/开启定义或在旧 generation 补跑；只有旧定义正式退休、Receipt/隔离一致后才计划 direct successor。230 L0 继续挂起，m1 单写不 push，dev-org 仅零 canary。

本波 `GREEN` 仅指未来 Cron 资格被正式关闭，**不**是恢复、退休或 A0-V 准入。任何后续 DB/Owner 状态漂移先冻结并只读对账。
