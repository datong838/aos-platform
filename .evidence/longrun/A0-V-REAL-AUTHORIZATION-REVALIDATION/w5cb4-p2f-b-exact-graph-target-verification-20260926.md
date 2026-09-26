# W5CB4 P2f-b 第 2/4 步中间验证｜exact Graph target

## 结论

- 新入口只接受 `logic_graph` 的 exact id/revision/hash 与提供的持久快照一致且内容等于审定的无 effect Graph；返回 `TargetExecution` 的布尔结果，不输出事实正确/合规结论。
- 隔离测试库经 `LogicGraphStore.create/get` 持久化并读回通过。错版本、错 hash、错 ID、未持久快照、篡改表达式、归档状态拒绝。
- 它不读 Publication/ReleaseGate，不能单独证明当前发布权威。生产元库、Provider/Worker、商城源、旧 Run 与 Plan 均未操作；正式 Suite/Contract 仍不存在于当前实例。

## RED→GREEN 与回归

- RED：新增 exact target 用例后，缺少入口时报 `ImportError`。测试 PG 首次因隔离租户工作区未建而触发 FK 拒绝，补齐一次性测试库租户 fixture 后重跑。
- GREEN：专项与邻近累计 `54 passed`；`git diff --check` 通过。后端无 UI 变更，浏览器验收不适用。

## 下一动作

- 第 2/4 步尚未结束：用正式 AIP API 在隔离 PG 建治理 Suite、EvalRun/Report、ReleaseGate、Publication，再冻结内容主体 Contract；交叉校验同一个 Graph target 与 Suite，拒绝撤销/错租户/伪发布。之后第 3/4 步才在新 Plan 创建前绑定，不能对旧 Plan 补票。
