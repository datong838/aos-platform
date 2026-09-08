# AR2-7D D1 配置行修订身份验证

- 基线94faeb8e/AOS-000571；m1同一Task/Lease，当前切片只建立meta_source实际行修订Owner，尚不绑定连接读取。
- 新增ar2_010：旧行仅建立当前基线；BEFORE生成不透明UUID，AFTER写实际变化历史；props/type/status/plugin_id实变产生新修订，no-op upsert/updated_at-only不产生候选history。历史不保存props、连接字符串或秘密摘要。runtime仅SELECT，双租户FORCE RLS；源删除保留历史，重建新身份。
- 模块缺失的Red后实现。独立复核发现临时表遮蔽：新增真实PG反例确认public历史count=0失败；改为本切片public全限定+pg_temp最后，反例恢复通过。代码终审无剩余阻断；此为本地只读审查，不是外部Prime PASS。
- 5专项+前序观察/质量/规范库完整回归95 passed（7 warnings）；新增迁移和拆列反证后8专项最终passed（7 warnings in 11.98s）。只在本次拥有的18434临时PostgreSQL及自动创建/删除数据库执行。
- 实测并发两连接同内容upsert仅1条历史、跨tenant canary零可见、运行角色INSERT/UPDATE/DELETE/TRUNCATE历史全部42501拒绝、token/identity重绑SC001拒绝、外层回滚不留记录、旧exact身份仍可回读、删除重建不伪造prior；正文/拆列/引用漂移拒绝。历史写入权限先于不可变trigger拒绝，测试明确校验SQLSTATE而非笼统异常。
- 实测ar2_009旧行升级到ar2_010可回读安全基线；非空降级拒绝且原历史保持；空库可降级再升级。配置行版本不证明vault秘密材料版本、连接缓存或上游快照。
- 闭包ar2-1扫描1697/分类85/迁移57，五类错误均零；git diff --check通过。仍不将ar2-1结果代替ar2-7切换验收。
- 迁移SHA256 dcf1c8cd26ee227cbfee7f57c8d35849f33de260b19f3cdb968658649005b1c2；reader cd58f707010926d219d004ff114e5bad3a7738bcffaec2ebf71f93404ce0d11e。
- 未升级任何共享数据库，未启动原18432，未读真实源、Provider或外部发布；未push，230 L0继续挂起。下一步在单次SQL快照取得props与修订并与读取观察绑定；D1及D2～D4/7E未完成。
