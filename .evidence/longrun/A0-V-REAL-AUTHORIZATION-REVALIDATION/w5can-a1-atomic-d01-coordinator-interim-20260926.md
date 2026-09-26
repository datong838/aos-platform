# W5can｜第 3–4/6 步中间证据（非波次完成）

## 已完成的代码与 RED/GREEN

前序 `1b63f480` 提供无提交的 AIP Owner 与 D01 来源 reader 事务入口。本次方案增补后，新建未注册的 `ecommerce_analyst_d01_atomic.py`：只接受原 `AnalysisContinuationOrigin` 与 `AipAgentRunService`；在唯一 tenant 连接中用原链回调检查 AnalysisRuntimeReceipt 的 TaskRun/Plan/cutoff，使用同一个 `HostTransaction` 读取当前 TaskTimeline/来源包并调用原 Owner 的私有无提交写核心；原键 Receipt 独立回读后，外层才提交。未知提交异常直接上抛，不换 ID、不重发。未接 Host、未调用 Provider。

RED 已记录：coordinator 模块缺失；approved Plan content_hash 漂移被旧 issuer 接受。GREEN：复用 AIP Task Store 原 `_canonical_hash` 拒绝漂移计划；单元测试覆盖原链/Plan/cutoff/来源拒绝、同事务对象、Receipt 回读缺失、提交未知。原 AIP6 隔离 PG 用例进一步证明借入事务的 AgentRun/Receipt 回滚与同键重放仅一行。

## 回归与边界

原链 PG fixture 使用事务开始时间伪造事件；在 sourceGroup 分支会早于 cutoff，触发 `startup evidence chronology differs`。仅将该分支的测试合成事件时间设为原 command cutoff，未修改生产时间规则。含该 fixture 的累计回归：92 passed、3 skipped；原链三套 PG 复跑 20 passed。`py_compile` 与 diff 格式检查通过。

以上仍非真实自然业务证明：coordinator 的成功样本使用注入式来源/Owner 测试，尚无同一隔离 PG 的原链+当前真实 D01 packet+Owner 组合、当前 packet selector、预算/模型/Host 注册、自然 D01 结果。真实 PG 缺 running TaskRun/MethodRevision，浏览器自然结果未验收。下一步 W5can 第 4/6 步继续补完整隔离 PG 组合与来源选择；条件不足则明确冻结 Host，并将可独立推进的 D02/D03 或内容 Handoff 核心切片进入下一波。旧 12 Run 不重播、商城源不读、230 L0 挂起、dev-org 零 canary。
