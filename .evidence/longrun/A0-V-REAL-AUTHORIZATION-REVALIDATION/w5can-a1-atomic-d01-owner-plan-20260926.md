# W5can｜A1 D01 原链、来源、Owner 同事务接线方案

## 复习上位方案与现场

231 A1-02/03 要真实自然触发的 Case/Run、建议来源和内部 Task/AgentRun；231-9 BG-02/03 不接受手工拼接或无依据建议。栖月汇产品方案要求经营参谋是现有八工作台之一，不新增第九菜单。W5cam `d7b769a7` 只提交精确来源包与 Receipt 发现预检，Host 未注册；真实 PG 缺 running TaskRun/MethodRevision。旧 12 Run、230 L0 均不作为本波输入。

源码现场：`AnalysisContinuationOrigin.run_current(conn,receipt_ref,execute)` 在同一连接内复核原 Occurrence/Case/Run、控制 Receipt、初始化 Evidence、当前身份与安装代际；`AipAgentRunService.create` 目前自行打开连接并 commit，无法安全嵌入上者。W5cam 来源 reader 亦单独开事务。**不能用前后各查一次来声称同事务。**

## 文件级清单与 1–6 步

1. 审查 `services/aos-api/aos_api/aip_agent_run_service.py`、Registry Store 的锁/Receipt/commit 语义、`ecommerce_analysis_continuation_origin.py` 与 D01 source reader；确认可注入同一 scoped connection 且不改变公开 `create` 路径。先用测试证明旧 create 行为。
2. 在 `services/aos-api/tests/aip/` 与 `services/aos-api/tests/extension_runtime/` 写 RED：原链变化、来源撤权/缺包、Owner 失败、重复键、未知提交均不得产生第二 AgentRun；同事务回滚必须撤销试写，原 Receipt 可只读对账。若 DB/Owner 事务合同不能复用，停止代码并更新方案。
3. 最小接口变更：现有 Owner 抽出“借入连接且不 commit”的同步内部方法，公开 `create` 继续管理连接/commit/错误映射；W5can coordinator 在 `AnalysisContinuationOrigin.run_current` 回调内读取同连接 D01 packet/当前身份，调用 Owner 内部方法，原事务外层统一提交并读回 Receipt。严格限定 A1 D01、稳定 key，不开放通用绕过接口。Provider 默认关闭。
4. 专项 + AIP Owner/原链累计回归、隔离 PG 撤权/重复/回滚验证；先解决或明确隔离 `startup evidence chronology differs` fixture 时间线，不以 mock 绿替代 PG。
5. 仅有新鲜真实 TaskRun、MethodRevision、批准 Plan、预算/模型/安装权威时才做 Host 只读浏览器/自然发行验收；否则保留 Host 未注册并如实记阻断，转做下一个独立首链核心切片。
6. 方案/代码一致性复审、verification、m1 commit、AOS/Prime 上下文同步；自动进入 D02/D03 或最早未闭合的 A1 核心波。

停止门：未知提交不重发、不换键；旧 12 Run 不手动重播；不读商城源；权限/时钟/来源/原链任一不可证即无发行。m1 单写者、不 push、dev-org 仅零 canary。真实执行仍须另证预算/能力/审批，不因 AgentRun queued 而假定成功。

## 第 1 步接口复审细化

Owner `create` 直接在自有连接里 `commit()`；不能向它塞一个共享连接工厂再代理掉 commit。最小可行接口是在 Owner 内抽取接受 `HostTransaction` 的无提交写核心，保留公开 `create` 的原连接、异常映射和 commit；写核心必须在执行 SQL 前核对事务内 `aos.org_id`/`aos.project_id` 与 scope，拒绝错租户。W5can coordinator 由原链 `run_current` 持有同一 raw connection，向无提交写核心传 `HostTransaction`；来源包读也须改为同事务入口，不再独立开连接。RED 首测无提交/错租户/原公开 create 不回归，然后隔离 PG 证明回滚、原 Receipt 唯一和权限撤销。任何 HostTransaction 包装都不是单独授权，只有原链回调内才可发行。
