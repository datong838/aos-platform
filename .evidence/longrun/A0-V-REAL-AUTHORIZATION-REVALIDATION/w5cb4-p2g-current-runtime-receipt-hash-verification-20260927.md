# W5CB4 P2g｜当前内容 runtime Receipt 全命令哈希修复与同库子证明

- 原先 `m1@25e162bd` 的隔离 Budget held 测试基于 `a0v_011` 模板手动补 `012/013`，不是完整迁移；已在两份原 verification 中增记更正。本波新测试先对名称为 `a0v_growth_graph_test_*` 的精确一次性克隆使用正式 Alembic 升级至代码 head `a0v_105`，读回版本及 `extension_dispatch_lock_group_a0v_028(uuid)` 存在；未迁移当前业务库。
- RED：正式 `BoundEcommerceGrowthRuntimeStore.put` 写入原内容命令的 PENDING Receipt 后，`ContentReviewPendingReader._current_dispatch` 把完整命令哈希误同内部 `command.requestHash` 比较并拒绝。代码修复仅在候选读取器、`CurrentContentPreparation` 和 `ContentGenerationStepOwner` 三处改用正式 runtime writer 的 `_request_hash(command)`；保留内部 hash、Receipt 格式和全部权限约束。相邻单元 fixture 按正式 writer 哈希更新。
- GREEN：同一克隆库中原 Task/批准 Plan/运行 Run → held 预算 → `ContentExecutionJournal.enqueue` → 正式 runtime Store PENDING Receipt，journal/Receipt 同命令 replay 不复制；候选的当前 dispatch 只读核验通过，改命令或禁入 runtime 后拒绝。写侧准备和 StepOwner 用测试接缝证明已越过哈希门；**未**模拟通过完整 Host cutover-group 锁。完整锁要求非超级用户、serializable 和九操作组，此夹具仍未具备。
- 专项 `2 passed, 7 warnings`；内容与邻近 Worker/EvalRunner 累计 `289 passed, 35 skipped, 7 warnings`；`git diff --check` 通过。测试结束后只读查验临时 `a0v_growth_graph_test_*` 库为 0。失败过程中遗留的一份确切测试克隆库，经无会话与名称双核验后已删除；可由重跑测试重新创建。纯后端，无浏览器改动。
- 这不是 settled Provider/Usage/Artifact/TAOR/Eval/ReviewIssue 同一 reservation 全链，也不是现有栖月汇安装的运行授权。无真实 Provider 外呼、生产数据库写入、Worker 启用、商城源读取或旧 Run 重放。下一步应补合法 Host 锁测试环境及受控结果/结算；若全锁夹具耗时过高，先保留缺口并继续不依赖它的首链 Owner 编码，不能将本段 GREEN 当上线门。
