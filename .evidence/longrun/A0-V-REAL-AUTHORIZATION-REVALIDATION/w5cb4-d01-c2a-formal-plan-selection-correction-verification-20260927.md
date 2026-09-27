# W5CB4 D01 C2a：正式 Plan Schema 与后置来源批准分层修正证据（2026-09-27）

## 结论和边界

**C2a 代码与隔离数据库门通过；C2 完整联合正向仍未完成。** `compile_stage_template` 的正式 PlanStep 仅含阶段 `inputSchemaRef`，不含运行后才形成的 Method/Query/EvidenceBundle 等 exact 引用。此前要求 Plan `inputRefs` 等于 D01 packet 会使正常编译 Plan 永远无法进入 D01；原 C1 的隔离正例使用了非正式编译样式 Plan，不能据此称自然链可用。本波修复为双审批：原 Plan 批准阶段/Schema/责任人；独立 `D01SourceSelectionApproval` 批准完整 packet，必须绑定原 TaskRun/Plan hash/SourceSelection 与不同 checker。AgentRun 输入仍必须与 packet exact 相等。

## 执行与新鲜验证

1. 先修订 `w5cb4-d01-c2-full-owner-joint-proof-plan-20260927.md`，并在原完整包方案中撤销 Plan 集合等于 packet 的过时条款。新增正式编译样式 Plan 正向和缺选择检查器负向，实施前两项 RED；旧夹具经纠偏后一度 29 failed/27 passed，未计通过。
2. 最小改动：`ecommerce_analyst_d01_issuer.py` 强制当前选择回调、Plan 首步 Schema 一致、选择→现时来源→再次选择→原链复核后才调用原 Owner；`ecommerce_analyst_d01_source_selection_store.py` 的 propose/read_current 同步使用正式 Schema 门，保留已批 Plan/Run/hash/checker/撤销；`ecommerce_analyst_d01_atomic.py` 从同一个 serializable 事务向 Issuer 注入 `read_current` 选择读门，不增加 Host 注册、Provider 或新写接口。
3. 专项：Issuer、Atomic、Store、隔离 PG 四文件 `57 passed`；增加“来源读取后选择漂移仍零 Owner 写”负向后，相邻 D01/原链/Task/Portrait/AIP Owner 九文件累计 `108 passed, 7 warnings`。首轮累计命令误引不存在的 `test_ecommerce_analyst_portrait_inputs_pg.py`，退出 4、未执行，不计绿；按 `rg --files` 改用真实 `tests/test_ecommerce_analyst_portrait_inputs.py` 后全量重跑成功。`git diff --check` 通过。
4. 隔离 PG 的真实两阶段选择测试已改为正式 Plan Schema 样式，并实测 proposal→独立 approval→同事务 read_current→revocation 拒绝。它**没有**合并当前 Method/Query/Bundle/Grant 与 AIP AgentRun Owner 写入，不能拼成 C2b 通过。
5. 本轮安全预览读回：8080 OpenAPI HTTP 200、8434 `/workshop` HTTP 200、18181 无监听；浏览器实际页面显示“当前有效安装 0 个／模块未安装”。先前浏览器检查仍是旧进程，不能证明改动热加载；下述提交后重启已单独完成。当前库 a0v_106，本波 a0v_107 仅隔离 PG；Host/自然 worker 继续关闭。

## 提交后每日最新栈再验收

提交 `cad0b905` 后，先运行最新源码安全启动器只读前置，返回 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、数据库 `aos_current_preview_20260927`/`a0v_106`、唯一 installation approved、四包 published、Runtime binding 0。精确 TERM 原 API PID 8783、精确重启 `colima-aos-extension/aos-a0v-recovery-pg` 容器（命名卷仍是 `aos-a0v-recovery-pg-data`）、精确 TERM 原 Vite PID 8459 由既有守护重起。PG `pg_isready` 成功；最新源码 API 新 PID 14052、Vite 新 PID 13984，8080/8434 HTTP 200，18181 仍无监听。安全启动器打印 migration disabled、Runtime Host 0、workers 0。浏览器 reload 后再次读到“当前有效安装 0 个／模块未安装／暂无可见工作台入口”，符合禁入；没有把 a0v_107 当前库能力伪称可用。未删卷、库或备份，未读商城源。

## 风险、待办与下一步

- C2b 必须在一个隔离 PG 真实贯通原 AnalysisContinuationOrigin→正式选择→现时 Method/Eval/Metric/Query/Bundle/Grant→AIP AgentRun Owner Receipt，负向覆盖撤销/权限漂移/未知提交；当前未有此联合证明。
- 保留用户已有 `test_ecommerce_content_review_pending_pg.py` 与 w5c8i 未跟踪文件，不纳本波提交；不读商城源、不回放原 12 Run、不手工 run_definition、不迁当前库、不删任何卷。
- 若 C2b 夹具成本越过有界预算，保留明确 RED，转 BG-00 首链合法绑定/配置主线；不把 C2a 当成 C2 完成。
