# W5c7m `_bound_parent` 子段透明探针方案（2026-09-25）

## 上位合同与输入

复习 231 总计划/231-5：真实自然运行、原代次与数据截面、当前权限及失败恢复不可凭测试或手工拼接替代。W5c7l 审计 `894edcc4` 只提出同一 `_load` 内可能的等价切片，未授权优化；W5c7k 旧长测正式超时，219 项累计回归通过。真实 A0-V closure 缺完整 Host universe/Fresh Owner，始终无自动动作。

## 文件级九步

1. 复习上述方案、`ec_ingress_recovery._bound_parent`、`ControlledIngressJournal.verify_running_schedule`、现有 opt-in 测试计时器及相关失败合同。
2. 本方案先提交；仅改 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py` 的 opt-in 诊断封装，新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c7m_bound_parent_substage_probe.py`。不改 `aos_api/` 生产代码、schema/DB/索引、部署。
3. 对 opt-in `_bound_parent` 计时，测试侧包裹 journal 的 `read`、当前 claim 读与 `verify_schedule_binding`/`verify_completed_schedule_binding`，分别记录次数与单调耗时；输出仅汇总，无 envelope/源数据。不得改变参数、返回值、异常、调用顺序；非 opt-in 不安装任何 wrapper。
4. 专项负例用 stub/monkeypatch 证明：parent 缺失时拒绝且不做 schedule；claim/绑定失败原样抛出且无重试；completed 与 running 分支选择不混淆。包括原 opt-in 透明测试。
5. 跑相关专项及 Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/j 累计回归；长例仅在有明确有界预算且需要真实子段分布时单次运行，超时不得计 GREEN；测试 PG 用后停。
6. 浏览器只读 rev4 disabled；不保存/运行/冲刷队列。
7. 复审探针本身无额外业务查询、无数据泄露或 fail-open，并对照 W5c7l 审计标明哪些优化仍未获证。
8. verification 提交后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆，读回一致性。
9. 下一波 W5c7n：依据子段实测与负例决定是否仅做同事务等价性证明/隔离 PG 对抗测试；不得直接删除校验或启动真实 closure。

旧 attempt 不重发、不手工 `run_definition`；商城源行不读；230 L0 挂起；dev-org 零 canary；m1 单写不 push。
