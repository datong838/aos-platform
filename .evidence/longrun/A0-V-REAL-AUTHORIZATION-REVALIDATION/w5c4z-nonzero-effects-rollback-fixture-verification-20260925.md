# W5c4z 非零 effects/事务回滚隔离核验（2026-09-25）

上位 231 A0-V/231-9 BG-00；方案 `12f0a78b` 先行，测试 `7c7831ca`。真实原组未被关闭，本波只在自动销毁的隔离 PostgreSQL 调用原 `a0v_091`。

## 九步证据

1. 复习正式 SQL、原定义/计划/组 claim Owner、W5c4y 与严格 24h 门。
2. 文件仅本方案、`services/aos-api/tests/extension_runtime/test_a0v_w5c4z_nonzero_effects_pg.py`、本 verification；生产 Owner/迁移零改动。
3. 原 Owner 在同一隔离组生成 12 schedule Run、1 group claim、12 group member、12 source claim；Run fixture 置于 DB clock-25h，随后禁用定义。
4. 仅测试事务安装故障触发器，令正式 SQL 写 Receipt 后的 Run UPDATE 抛 P0001；保存点回滚后 Receipt=0、12 Run running。撤去故障后原 SQL 唯一成功：`businessAccepted=false`、effectEvidence 对应 1/12/12；原 group claim/member/source claim 行仍在，12 Run failed。没有生产 SQL 改动。
5. 定向 **1 passed，7 warnings**；W5c3/W5c4、定义、attempt、lease、preparation 有界累计 **191 passed，7 warnings，24.00s**。最后只调整测试断言写法，定向重跑通过。隔离测试数据库已停止。
6. 5174 浏览器只读见 12 单路计划和整组入口；页面无法证明后端 rev4/关闭门，`BROWSER_PARTIAL`；无保存、运行、队列冲刷，临时页面与前端已关闭。
7. fixture 非零 group/source claim 与真实同类，但 group input、ingress command 等类别未在本波构造，不能宣称七类 effects 全量覆盖；真实组只读仍 `STALLED_WAIT_24H`、`automaticAction=false`，严格最早在 `2026-09-25T20:00:04.800482+00:00` 后。无真实 Receipt、Run、定义改动。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5a：继续剩余 effect 类型/真实门禁预检债；严格 24h 到线时先独立真实关闭方案、新鲜全门禁，再唯一调用正式 Owner、独立核验和定义退休。未知提交边界冻结不重发。

m1 单写、不 push；不读取商城源行；旧 attempt 不补跑；230 L0 挂起，A0-V/BG-00 未过。
