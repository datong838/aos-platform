# AR1-c 验证提交与旧入口隔离检查点

2026-09-06；基线 m1@63b5d170 / AOS-000525；主 Lease AR1-C-LIFECYCLE-PERSISTENCE，旧消费者子 Lease AR1-C-LEGACY-RUNTIME-BOUNDARY。

内部验证提交在同一事务校验当前安装修订、验证操作 CAS、当前权限回调、签名与资源证明、准备提交证明、健康时效和条件回调；原安装验证事件、disabled/ready/fenced binding、操作事件与 outbox 原子落账。不提供 HTTP 入口，不自动启用，不赋予业务执行权。当前权限和条件的正式生产读取接线、持有者验证调度、重启恢复仍未完成。

旧工作台目录、职责模板、本体读取/overlay 和集成创建消费者排除运行扩展及缺失或漂移的注册表内容；先计算替代关系再过滤，避免旧父安装复活。纯内容旧路径保留，历史审计不隐藏。

验证：验证方法缺失 Red；关联准备锁反证 Red（跨验证操作导致 statement timeout），改为同安装且 runtime-apply 条件先筛选再锁定。目标 16 passed / 24 deselected / 19.89s；旧消费者目标 37 passed / 7.60s。累计 extension_runtime 加原有九组 asset_registry 单测、职责模板和目录回归：494 passed / 6 既有 warnings / 88.91s / exit 0。真实隔离 PG、签名 Registry 和 OCI worker 组合完成准备到内部验证；binding 保持禁用且有栅栏，旧目录不暴露运行能力，停止后资源释放且 binding 变为 unknown。独立 Prime 只读复审未发现新实质问题；未代替执行测试。

内置浏览器只读冒烟打开 http://127.0.0.1:5173/workshop/analyst，页面加载并显示 org-org/dev-project；仍无正式分析记录。没有刷新后端服务或证明其已加载本次代码，因此不作为新后端浏览器验收或八页面功能完成证据。无本次前端变更。

仅使用专用隔离容器与临时数据库 schema；无共享数据库迁移、真实业务数据写入、Provider、费用或发布。新增闭合业务场景 0，整波仍 IN_PROGRESS。下一施工段：持有者验证调度和当前条件读取，再推进受控配置/启用与恢复。
