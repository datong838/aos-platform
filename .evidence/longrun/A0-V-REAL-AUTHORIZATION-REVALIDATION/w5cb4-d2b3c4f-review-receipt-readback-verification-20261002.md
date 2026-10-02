# d2b3c4f 新来源 Review Receipt 读回验证

## RED 与最小改动

按同名前缀文件级计划先写单元合同。`services/aos-api/.venv/bin/python -m pytest -q .../test_ecommerce_review_advance_host.py -k accepted_stage_receipt_readback_requires_exact_persisted_command` 首次 exit1，`1 failed, 25 deselected`：`accepted-stage-v1` 的 `verify_receipt` 固定返回 `{}`。随后只修改 `ReviewAdvanceHostService.verify_receipt`：按 scope/key 读已有 Receipt，校验调用方回执相等、租户推导 UUID5、回执 body 自哈希、请求 hash、17 项源 lineage、ACCEPT/无 RETURN 与零外部副作用。原 `revalidate`/`execute` 禁入未改，旧来源分支未改。测试替身仅是读回合同单测，不是持久原生产者证明。

## 本次新鲜输出

- 专项+Task/Brief PG 邻接：`33 passed, 7 warnings`，exit0。
- 原 Stage/Handoff 与内容生成邻接：`47 passed, 7 warnings`，exit0。
- `py_compile` 与 `git diff --check`：exit0。
- `curl http://127.0.0.1:8080/v1/health` 和 `/v1/ready`：200/200；`http://127.0.0.1:8434/aip/skill-publish`：200；18181 无监听。先探 `/health` 得404是错误路径，已按已有重启证据使用 `/v1/health` 复核。
- 内置浏览器当前页面：37 项仅评测、已发布0；三项 blocker 为正式技能发布放行、当前业务 Logic、可用模型路由/策略，按钮 disabled；电商导航“暂无可见工作台入口”。

## 复审与限制

本切片只使未来**已由原生产者持久化**的新来源 Review Receipt 具备精确读回能力。原 AnalysisRuntimeReceipt/Stage TaskRun/Plan/Eval/Artifact/permission 与当前 Case/Occurrence 联合、原 Review producer 同事务持久化、ContentGenerate/Review 原消费者正向、E17 当前正式身份/配置/Owner/发布/绑定与自然首链均未完成。没有读商城源、当前真库写、旧 12 Run 重放、手工 Run、Host/worker/Provider 启动或 push。下一波继续原合法 Review producer 的 Stage runtime/Eval/permission 源矩阵及可销毁 PG 正反链；若正式 E17 来源到位则转当前实例准入。
