# W5c8i｜隔离 PG unknown 原 attempt 同事务授权原型计划

## 上位与当前停线

承接 231-5/6、W5c8h 审计 `m1@c70fa680`、AOS-000670。真实 Colima `aos-extension` 停止，组合门冻结；本波绝不启动真实 profile/Host、迁移真实库或调用真实 `reconcile_completed`。W5c8g 只读诊断与写事务必须分离；旧 `a0v_050` 运行角色 EXECUTE 是旁路。过期 `claimed` 另波。

## 文件级施工范围

- 测试环境：先检查 `colima list` 和 5433 空闲；只可创建全新、从未承载真实 A0-V 的独立 profile `aos-a0v-test-only`，在其中启动显式 `--restart=no` 的一次性 PostgreSQL 16 测试容器。不得启动已有 default/aos-extension profile 来碰未知自启容器。退出时只停本波新容器/profile，记录是否有遗留；不碰别的容器/卷。
- 首先新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c8i_unknown_reconciliation_contract_pg.py` 的 RED：在隔离 PG 建原 unknown 完整链后，要求新受控入口对同 Host/current tuple/双 Receipt/保存源组成功，对错 token/epoch、源组、前置 Receipt、租户、旧函数旁路、过期 claimed、并发失权全部拒绝且零二次 source 调用。若完整链夹具太重，先分拆以真实 SQL 合同为核心的窄 PG 测试，不以 mock 冒充成功。
- 仅在 RED 与锁序审计成立后，候选新增 `services/aos-api/alembic/versions/a0v_096_*` 与 `services/aos-api/aos_api/data_requirement_outbox_store.py` 显式 opt-in；旧 Worker 默认路径不改。迁移须在同一写事务先 `a0v_094` Host fence，再验证源组/原谱系/双 Receipt 和 Delivery 原 attempt；撤运行角色旧 `a0v_050` unknown 对账 EXECUTE，防新旧并行旁路。所有函数输入 exact 且租户双键一致，重放/未知提交只读对账。
- 若 SQL canonical hash 与 Python Locator 语义、Host→Delivery 锁序、或旧入口撤权/兼容不能完整证明，本波按 RED/STOP 收笔并登记 W5c8j 缺口，绝不发明“近似授权”代码。
- verification、D-waves、AOS 上下文、Prime 更新与 m1 提交；不 push。

## 九步

1. 复习 W5c8h、原 SQL/Store/Locator/Host Lease、产品恢复约束，核 Git/authority/测试环境。
2. 本方案先提交，固定独立测试 profile 和零真实 effect 边界。
3. 建安全隔离 PG；先写 RED 负例/正例合同。
4. 如 RED 确认且权限/锁序可行，做最小默认关闭实现；否则按方案 STOP 分支写审计。
5. 专项 PG + 近期短累计；测试库 0、无真实数据库连接。
6. 浏览器仅只读记录真实服务状态；若租户目录仍不可用，照实标不可验收。
7. 方案/代码一致性与安全复审，特别旧函数旁路、Host TTL/锁、上游 Store 效果范围。
8. verification 落盘/提交、AOS CAS、Prime 回读。
9. 自动下一波：GREEN 时 W5c8j 独立评审生产接线/真实迁移前置门；RED/STOP 时 W5c8j 针对确定的授权缺口继续设计/修复。真实 closure 始终另立 gate。

230 L0 挂起、商城源不读、dev-org 仅零 canary、未知结果不重发/不手工 `run_definition`；m1 唯一写者，不动其他分支。
