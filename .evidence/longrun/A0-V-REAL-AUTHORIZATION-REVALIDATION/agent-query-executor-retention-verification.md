# AgentRun 原始 Query 执行期留存验证

2026-09-11，基线 `m1@cc65dbe6`。

受治理 executor 的显式正文留存模式现在同时留存输入与输出；默认模式保持不留存输入正文。
输入 Artifact 在 PREPARED Attempt 创建后、任何 lineage reconcile 和 Provider 调用前写入，
Artifact ID 由 tenant、Attempt 和类型确定性生成。通用 payload 仅有 hash、marking、来源与
长度，原文只通过 `text_content` 进入私有 `aip_agent_query_input` Owner。输出 source 新增
同一 Attempt 的 requestHash。

故障注入验证中，私有输入 Owner 抛错后 Provider 调用数为 0，Attempt 从 PREPARED 转为
FAILED，reason 为 `INPUT_ARTIFACT_WRITE_FAILED`，AgentRun 同步为 FAILED。Provider 已调用后
的既有 Artifact/UNKNOWN 语义未改。

验证结果：

- executor、输入 Owner、输出 Owner：`75 passed / 1 skipped`，4.39 秒；
- D01/D02/D03 生成、receiver、worker、阶段评审联合回归：`483 passed / 21 skipped`，
  9.08 秒；
- 显式启用 disposable PostgreSQL 完整图：`26 passed`，5.97 秒；
- 两个修改 Python 文件编译通过，`git diff --check` 通过；
- `verify_closure.py --phase ar2-7`：扫描 1,764 个 Python 模块，分类 127，迁移集合 85，
  hash、正向、反向、跨层导入和动态引用错误均为空。

skip 均为需要其他显式环境开关的既有场景；数据库完整图已经单独显式执行。本波未调用
真实 Provider、未产生真实业务 mutation。下一波读取 query/output Artifact，并用包内规则
派生正式 Eval case，补齐生成输入与阶段评审之间的可证明同源链。
