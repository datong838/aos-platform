# W5c5a group input / ingress effects 隔离核验（2026-09-25）

上位 231 A0-V/231-9 BG-00；方案 `4ca75129` 先行、细化及测试 `ec795d48`。真实 group 未关闭，生产 Owner/迁移不变。

## 九步证据

1. 复习 `a0v_045` journal 完整性、`a0v_091` effectEvidence、受控空观察路径与 W5c4z。
2. 文件限本方案、参数化 `services/aos-api/tests/extension_runtime/test_a0v_w5c4z_nonzero_effects_pg.py`、本 verification。
3. 在 W5c4z 的原 Owner 12 Run/12 source claim fixture 上，用 `ControlledIngressJournal.save_empty_for_running_schedule` 保存 12 个合法 empty observation；group input 使用原 journal 格式并通过原延迟约束即时校验。没有读取商城源行或模拟非空数据。
4. 两变体都先用测试专用触发器证明正式 SQL Receipt 写入后 Run UPDATE 失败会整段回滚，再撤故障唯一成功；有空观察变体的 effectEvidence 为 group claim=1、group input=1、group member=12、source claim=12、ingress command=12，原效果行均保留、业务未接受。
5. 定向 **2 passed，7 warnings**；有界累计 **192 passed，7 warnings，30.01s**。隔离测试数据库已停止；更宽慢集此前中止不算 GREEN。
6. 5174 浏览器只读复核 12 单路计划与整组入口，`BROWSER_PARTIAL`；不点击保存/运行/队列冲刷，临时页/前端已关闭。
7. 本波覆盖空观察效果类别的计数与保留，不证明非空业务数据、derived command、dataset receipt，也不等同真实组关闭。实时只读仍 `STALLED_WAIT_24H`、`automaticAction=false`，严格最早在 `2026-09-25T20:00:04.800482+00:00` 后。原 12 Run/定义 rev4 禁用不变。
8. 本 verification 先提交，再 CAS 同步 docs/AOS 项目开发上下文及 Prime 独立受管记忆并读回。
9. 下一波 W5c5b：继续剩余合同与真实关闭前只读预检；到线时另立独立方案、新鲜全门禁、唯一原 Owner 动作，独立核验后正式退休。

m1 单写不 push；商城源行不读；旧代不补跑；230 L0 挂起，A0-V/BG-00 未过。
