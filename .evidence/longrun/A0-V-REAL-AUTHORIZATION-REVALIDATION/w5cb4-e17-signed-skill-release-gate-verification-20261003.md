# W5CB4 E17-s2｜签名 Skill ReleaseGate 事务消费验证

## 实施与 RED

- 先读 231/231-3/231-9、56/64、553 和原 ReleaseGate/SkillPublication 调用，再写 `w5cb4-e17-signed-skill-release-gate-plan-20261003.md`。新增隔离 PG 测试首次运行 exit1：原 `derive_gate` 对有效双签 Skill Report 抛 `formal Skill Eval executor authority unavailable`，说明 RED 命中原硬门。
- 最小改动 `aip_release_publication_service.py`：derive/publish 默认使用原 `connect_serializable(scope)`；Skill 分支在同一事务调用 E17-s1 原持久 proof 装配并以数据库 transaction timestamp 核验。缺/错/撤销 proof 映射原 `AipReleaseGateRejected` 文案；普通 LogicGraph、revoke、普通 Eval Runner 和 request shape 均不改。注入连接不被自动提升，若隔离级别不足由 proof reader 禁入。
- 初次邻接回归暴露原断言依赖旧错误文案及测试固定 ID 互撞；保留原文案，测试 teardown 限定 `aos_test_*_ti4_test` 后按租户精确清理隔离签名夹具。未清理当前真实库或历史证据。

## 可复核证据

| 项 | 结果 |
|---|---|
| 隔离签名 Gate | 新增 `test_aip_release_publication_signed_skill_pg.py` 1 passed，exit0。test-only 双签 Suite/Run/Report/sidecar 导出 PASSED exact Gate；因尚无 evaluated SkillTemplate，发布尝试明确 `skill template revision not found` 且 Event=0；Target 身份撤销后旧 Gate 不能 mint Event、新键 Gate 也拒，Event 仍0。 |
| 相邻回归 | `test_aip_release_publication_signed_skill_pg.py`、原 ReleaseService/API、SkillPublicationService、E17-s1 装配共 `28 passed, 1 xfailed, 7 warnings`，exit0；原 xfail 不计通过。 |
| 静态/现场 | `py_compile` 两个目标文件与目标源码 `git diff --check` exit0；8080 `/v1/health`、8434 页面为200，18181无监听。页面/API 存活没有证明本次新代码已重启装载或业务通过。 |

## 方案复审与未完成

- 与方案一致：只让同事务签名证明取代无条件 Skill 拒绝，仍须原 Run/Report/Suite、Gate 阈值、当前撤销、exact target 和 PublicationEvent 原路径；没有接受请求自报 proof 或打开普通 callback Skill Runner。失去签名/稳定事务仍失败关闭。
- `AipReleasePublicationService.publish` 的签名校验与 Gate/Event 同事务路径已执行撤销负例；**正向 Event 尚无 evaluated Skill 原来源**，不能宣称 Skill 已发布。原 `AipSkillPublicationService.publish_evaluated_revision` 仍用 read-committed 连接调用此签名 reader，会失败关闭，须下一波单独修到稳定同事务并以原 evaluated Skill/Logic/Route/Policy 来源验正向。
- 当前正式 EvalRun Owner、issuer/Target/Judge 身份、受限 writer ACL/凭据、六 active Binding 和 frozen Plan 均未证明；当前真实库只读、Host/worker/Provider 关闭，自然首链 pending。
