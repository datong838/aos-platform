# W5can｜A1 D01 原链—来源—Owner 同事务核验与停点

方案 `040aa404`，实现 `1b63f480`、`5cf4f36e`。本波交付的是**未注册的安全接线**，不是自然 D01 业务结果。公开 AIP Owner `create` 行为保留；私有借入事务写核心和 D01 来源 reader 在同一租户连接内运行。`NaturalD01AtomicCoordinator` 仅接受原 `AnalysisContinuationOrigin` 和原 Owner，对原 AnalysisRuntimeReceipt 的 TaskRun/Plan/cutoff、当前 Plan hash、来源权威及原键 Receipt 回读进行门控，外层才提交。未知提交不换键、不补发。生产 Host 未注册，Provider 未调用。

专项测试覆盖原链漂移、来源缺失/撤权、Plan hash、Owner 失败、Receipt 缺失/重复、回滚和未知提交。隔离 PG 借入事务验证回滚不留下 AgentRun/Receipt，同键只保留一行；原链 PG 20 passed。累计回归 92 passed、3 skipped；`py_compile`、diff 检查通过。旧 startup fixture 的 sourceGroup 事件时间调整仅在测试夹具，生产 chronology 不变。无新页面且 Host 未注册，浏览器 N/A。

**停点/剩余工作**：当前进程的只读探测没有权威运行库身份（runtime worker database identity 未配置）；默认旧库没有 `aip_task_run`。因此没有可信的新鲜 running TaskRun/MethodRevision，也没有从当前已批准 Plan/来源权威确定性选出 D01 packet 的生产 selector。尚未做原链+真实 D01 packet+Owner 的完整隔离 PG，也未验证预算/模型/安装、自然 D01 结果。不得注册 Host 或称首链已跑通。这个缺口移入后续 A1 自然 D01 续波；不把旧 12 Run、旧商品行、mock 绿作为替代，也不因它阻塞可独立进行的 BG-04 首链开发。

方案/代码复审：实现范围符合 W5can 同事务与失败关闭边界，但原方案第 4 步完整 PG 和第 5 步真实自然验收未达成，故 **W5can 安全子范围完成、自然业务验收未完成**。m1 单写不 push；旧 12 Run 不重播，不读商城源；230 L0 挂起；dev-org 仅零 canary。下一波 W5cao 检查 BG-04 的已批准 Brief→内容任务最早缺口，不触发外部副作用。
