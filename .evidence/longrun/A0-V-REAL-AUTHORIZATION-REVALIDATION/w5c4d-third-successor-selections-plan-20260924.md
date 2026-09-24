# W5c4d 第三继任者 12 SourceSelection 正式签发方案（2026-09-24）

W5c4c `33de74d7` 已在正式 Owner 当前性门禁下 12/12 回滚演练；私有 0600 material 固定相同第三继任者安装/代际/epoch3/配置、12 pipeline/schedule 与短窗 draft。正式库新 selection/control/binding 0/0/0，12 schedule off、旧 DR 定义 retired。

1. 重读 W5c3x/W5c4a、Host/三 held、当前预算/四来源/源配置/图与 12 draft 有效窗；12 新 selection key 与持久行均为零，canary/在途零。预检材料只用于当前性核验，不把干跑当执行权。
2. 对 `P01`–`P12` 依次以新唯一 key 和 `previous_ref=None`：每条先写 0600 精确 intent，再调用原 `PipelineControlServices.approve_selection` **一次**，结果立即单独 0600 保存。任一步结果未知，停整波只读按 key 对账，不执行余下条目、不重发；已有部分 selection 只保留为不可执行元数据。
3. 成功只认每 pipeline 唯一正式 selection revision/ref/hash、与对应 draft/当前安装/代际一致，12 schedule 仍 off，control/binding 仍0，旧定义 retired，业务计数不变。verification 落盘/commit。
4. 下一波单独建 12 runtime control；其后才绑 schedule、新 definition 配置/启用。绝不手工 Run、不读商城源行、不 push。
