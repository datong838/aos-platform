# 显式续租方案

适用 Rules：AOS engineering delivery、231八步、m1唯一写者、到期不删除未收口Lease。

背景：六项原Task已过期。Task与Lease必须精确一致，不能只修改Lease；到期不授接管权限。

候选：1. 同一Owner显式续租并保存历史；2. 原Task正式Delivery收口后登记新Task。当前恢复演练仍有未完成门，选择候选1的工具实现，暂不续租原业务Task。

修改范围：scripts/memory/memoryctl.py、scripts/memory/tests/test_memoryctl.py、此证据目录。无需改变恢复与观察器读者，保留其严格Task==Lease和未来到期校验。

契约：renew_task接收原Task完整expected_task、当前authority revision、原owner、新到期及非空归属复核说明。现有安装校验及排他锁内，精确检查Task、唯一Lease、Owner、ACTIVE、无Delivery、无其它重叠Lease、当前authority、带时区未来且晚于原到期。新记录仅改expiry。归属说明是操作者的审计输入，不等于工具自行证明线程或业务授权。

历史：以旧Task规范JSON哈希命名renewals/task/hash.json，保存完整before/after、当前authority及复核说明；先历史后Task再Lease并追加事件。历史不允许覆盖。任何部分写入失败不自动重试；严格读者因Task/Lease不一致或历史已存在拒绝执行，恢复须另行只读对账。多文件不是原子事务，不宣称崩溃自动恢复。

验证：真实RED缺失接口；正向expiry-only/history；foreign owner、stale authority、prior漂移、Delivery、overlap、timezone、past、不延长、partial-write拒绝及历史保留；相邻完整memoryctl回归。代码方案复审、精确提交和Delivery。原六Lease不变，真库/服务/Goal不变。
