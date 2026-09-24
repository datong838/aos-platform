# W5c2b 受控 installation 身份恢复与 DS 正式卸载（2026-09-24）

## 现场与最小决策

W5c2a `aad0fd12` 的一次调用在连接前因旧私有身份文件缺失而终止；同键 Command=0，DS active/etag5，新继任者 approved/etag3。PostgreSQL 现行角色 `aos_a0v_installation_20260912` 仍为 LOGIN/NOSUPERUSER/NOBYPASSRLS/NOINHERIT，且当前活跃连接 0；它是现有原 Owner 连接代码期望的 session_user，成员关系未漂移。禁止复制、猜测或打印旧密码，不创建超权限新角色。

## 固定顺序与文件

1. 新增 `scripts/a0v_w5c2b_identity_recovery.py`：先确认 W5c2a 新键仍 Command0、DS/新继任者状态未变、角色与成员关系/活跃连接精确；生成高熵随机密码，先冻结在新私有 0600 intent（不出现在日志），再在正式库一个事务内旋转**同一现存非特权角色**密码；结果未知时不重复，先用 intent 密码尝试只读登录/当前角色核验。成功后把本波受控身份文件 0600 落盘，并以非特权 session、`SET ROLE aos_app` 的受控连接只读核验；不使用 `aos_app` 超级用户身份执行卸载。
2. 新增 `scripts/a0v_w5c2b_ds_uninstall.py`：复用 W5c2a 的全部只读门禁，但使用新身份文件构造原 `InstallationService`/`RuntimeUninstallGuard`；以全新键 `a0v-w5c2b-ds-uninstall-20260924-v1`、全新 0600 intent 一次请求。W5c2a intent/key 永不重用。
3. 定向测试覆盖角色/身份作用域、缺文件拒绝、新键只执行一次；正式回读 DS uninstalled/activeRevision null、新继任者 approved、九路/12 调度/attempt/canary 仍零，verification、m1 commit、不 push。

## 停止条件

角色或成员关系漂移、其他活跃连接、密码旋转提交边界未知/验证失败、安装/路由/Receipt 任一变化或原 Owner 拒绝，停写并仅对账。旧角色密码变更可能使未观测的离线旧客户端无法再连入；当前无活动连接且旧身份文件已丢失，记录此风险，不把它当作业务授权扩大。成功后下一波才启动唯一独立 Host 做继任者 prepare/verify。
