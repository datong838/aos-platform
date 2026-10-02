# GW-b-2c2c1b3c2d2a｜内容生成原阶段来源命令禁入切片

基线 `AOS-001122` / `m1 0c78b3c2`，按 231-5 §9 与同名 plan 第1项。只改 Growth 包内生成请求、测试与方案，不改当前正式库、Host 或 Provider。

| 项 | 本次证据 | 退出码 |
| --- | --- | --- |
| RED 来源种类 | 新测试先以一个原 `Artifact` 构造 accepted-stage 请求；旧 dataclass 不接受 `source_kind`，`TypeError`，1 failed。 | 1 |
| RED 发送门 | 新请求形状出现后，原 `execute_content_capability` 把它交给 port，直到旧四源 Receipt parser 才以 `review response exact reference type drifted` 拒绝；说明发送前尚无禁入。 | 1 |
| 最小实现 | `ContentCapabilityRequest` 仅 `accepted-stage-v1` 允许一个原 `Artifact` 且命令含 `sourceKind` 进入 hash；默认 Issue 四源命令不加字段。`execute_content_capability` 在 port 前拒绝新分支；宿主 `_strict_content_generate_command` 也仍拒 `envelope drifted`。测试断言 port 命令0、Provider调用0，混源/未知种类拒绝。 | 见专项 |
| 专项/相邻 | `pytest -q`：`test_ecommerce_content_capability_budget_runtime.py`、`test_ecommerce_content_budget_command_owner.py`、`test_ecommerce_growth_host_ports.py`、`test_ecommerce_review_handoff_content_runtime.py`，在自动建销的 `aos_test_*_ti4_test`，89 passed/7 warnings。 | 0 |
| 静态/差异 | `python -m py_compile` 两改动文件；`git diff --check`。 | 0 |

复审：旧 Issue 请求和已有四 Artifact/预算/Receipt 路径保持原样。新 `sourceKind` 只证明包内可以准确表达一个原阶段 Artifact；没有当前 StageDecision/TaskBrief v3 原 Owner 同源校验，不能形成生成命令的合法执行权。包内与宿主双重拒绝保证在消费者未完成时零发送。浏览器仍显示工作台无入口、技能37仅评测/0发布且发布按钮 disabled；本后端命令波未改变页面。

下一项 `GW-b-2c2c1b3c2d2b`：先写宿主生成准入和回执 v3 来源合同 RED，核 Handoff/Task/Brief/原 StageDecision/Plan/Attempt/Eval/permission/时限同源；再接可读 Artifact 与内容评审双消费者，之后才评审解除发送门。当前 OIDC/独立身份、Host assignment、八配置、Growth1.13正式信任根/绑定仍为当前实例 P0。未启 Host/worker/Provider，未写真实库或 dev-org，未读商城源、回放旧12 Run、手工Run或push。
