# W5CB4 E05：当前卷从空业务态进入首链的正式产品入口审计计划（2026-09-28）

## 上位与进入事实

复习 231/231-9 的 A0-V→BG-01/02→BG-03/04 与“一个真实商品/客群/场景”。E04 已从产品入口取得描述性 MethodRevision r1，但这是配置元数据而非实际分析。当前同一权威卷的 `ecom_object`、正式 `projection_outbox` 商品事件、SourceSelection/RuntimeControl/ScheduleBinding、Occurrence、Task/Run、D01 proposal 均为 0（本波只查表级计数，不读商城源库或商品明细）。不可用旧卷补成当前运行事实，也不可手工造事件或 Run。

## 串行清单

1. 复习商品正式入库与 BG-00 数据源产品配置链：现有 DataConnection/SyncConfig、pipeline source selection/control/schedule 及 source-readiness Owner；只读核当前 signed installation、源配置/权限/预算门。区分“产品入口已有但当前 Host disabled”“缺可用源凭证或经营批准”“真正缺代码”。
2. 选择从当前空业务态出发的最小**可实施编码目标**，必须让获准的新商品源数据以后可自然进入 `ecom_object`/outbox；不能仅再加一个空状态屏。优先修现有产品入口的端到端断点，避免建立第二数据真源或绕过 Snapshot/SourceSelection Owner。
3. E05 若只读审计，则写 verification，明确 E06 精确文件清单、前 hash、专项/邻接/浏览器验收和是否需用户新的源读取授权；提交后立即 E06。若可直接在 E05 安全实现，先补本计划文件门再编码。
4. 当前 8080/8434 维持运行；本波不启动 Host/worker，不读取商城源库，不发 source approval/任务执行 POST。复核历史 12 Run 冻结和新方法 r1 互不冒充。

## 退出/停止

只有可回读的**当前** SourceSelection、合法快照来源和自然触发才可计入 A1；空表/旧证据/方法元数据不计。如果真实数据必须读取商城源库，先给出精确权限与最小范围的用户决策门，同时继续完成不依赖此权限的核心编码；不在未知结果边界重发。
