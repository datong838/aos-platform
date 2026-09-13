# UQ3-D 非超级宿主同事务快照验证

2026-09-13，基线9aaaef66。ui_read_api_database抽取仅两个固定函数名的principal包装，API仍032、宿主独立033。analyst_workspace_snapshot保留旧入口，机械共用范围/隔离校验及原查询组装，新增宿主入口先用受限principal函数锁当前身份再读canonical源。

21 passed、7项既有warning：新增非超级宿主快照2项、旧快照6项、API接入13项。固定角色仅canonical SELECT、受限身份函数，无成员UPDATE；有效Case/Run/State输入包纯投影得到1 Case/1 Run；第二连接插入在同事务不可见、下事务可见。API角色和主体不符拒绝。该canonical数据为真实隔离PG夹具，不是栖月汇经营首链。AR2扫描1844模块，163分类、93迁移，各错误集合为空。

主库与原宿主仍未部署新迁移。下一波组合具体UiReadConsumer：角色隔离事务、当前签名目录、同快照、单次claim、原PreparedJob签名读取、完成前当前身份/目标重查，再接RuntimeHost关闭/恢复路径；新包固定只读方法尚待签名交付。
