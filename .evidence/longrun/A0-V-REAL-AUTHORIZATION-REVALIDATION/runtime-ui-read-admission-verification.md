# UQ2-B 当前签名资源门禁验证

2026-09-13，基线e4da3721。具体RuntimeUiReadAdmission重新读取当前成员及markings，再调用既有RuntimeWorkshopCatalog加载签名模块，核唯一模块、scope、权限、七字段目标及readOperationClaims，然后进入原入队存储。同键回读不豁免当前门禁。

25 passed：13项接入PG测试（目录输出替身，真实成员与存储）及12项既有签名目录测试。覆盖旧摘要/epoch/路由、错租户、重复/缺失模块、角色/marking不足、command-only、撤销成员与旧键回读。目录替身不作为真实签名包已交付证据。AR2扫描1841模块、163分类、93迁移，各错误集合为空。

仍未开放HTTP或API写角色权限。当前成员FOR SHARE需要数据库受限函数接点，不能为此给Web身份授予成员表UPDATE。下一波UQ2-C建立专用只读投递角色的固定函数：当前成员/marking锁、受限入队；禁止Attempt/claim/result直接DML。主库仍不迁移，最终宿主消费仍须重新校验全部事实。
