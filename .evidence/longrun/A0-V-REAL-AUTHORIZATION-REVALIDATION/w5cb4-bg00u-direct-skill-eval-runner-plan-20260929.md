# W5CB4 BG-00u｜直接 Skill Eval Runner 准入方案

## 来源与范围

231 首链与 AIP-4 E1B 要求来源可复验的 Eval，不以 callback 自报或哈希相等代替正式执行身份。BG-00q 只在 `run_by_contract` 拒绝无独立 Judge/Target signer、撤销与执行 Receipt 的 Skill；`run()` 仍可凭调用方 `execute_target/execute_judge` 在建 EvalRun 后写 Report。BG-00r/s/t 后续 Gate、发布和 Binding 会拒绝这种 Report，但持久化假正式 EvalRun/Report 本身仍是来源混淆。当前权威库栖月汇 Suite/Run/Report `0/0/0`，无须清理历史行。

## 文件级方案

1. `services/aos-api/tests/aip/test_aip_eval_runner.py`：隔离 PostgreSQL 添加直接 `run()` Skill 的 RED：Suite 为 exact Skill 引用，调用方回调本可返回相等 ref；预期在回调及 EvalRun/Report 写入前拒绝，Logic 既有成功路径不变。
2. `services/aos-api/aos_api/aip_eval_runner.py`：取同租户 Suite 后、`create_eval_run` 前对 Skill target 做与正式入口相同的失败封闭。保留 Logic/其他旧目标和 `run_by_contract` 现有行为，不引入 signer 假源、迁移或当前库写入。
3. `services/aos-api/tests/aip/test_aip_skill_publication_service.py`：原三项历史负向测试的旧 Skill Report 由直接 Runner lambda 生成。改用隔离测试库的明确历史 Run/Report 行种子，测试仍证明“已存在旧行也不能再 Gate/发布/发行”；严格 xfail 正向链继续记录缺正式授权，不能当真实通过。测试种子不进入产品路径。

先 RED，最小实现，Runner/E2/Skill/Binding/目录相邻回归；签名 API 最新代码预检和重载。当前业务 DB 只读，PG/Web 不作第二次全重启，Host/worker/Provider 保持关。正式 Judge/Target producer、签发 Owner、撤销、执行 Receipt 和 G2 对象来源仍未齐；下波要从隔离正式权威合同与可恢复迁移设计推进，不借用 bundle 签名或测试 lambda。
