# AR1-c 可信目录与三平面身份预检检查点

- 日期：2026-09-06
- 基线：178cf123
- 业务场景计数：0
- 页面变化：无；浏览器验收不适用

## 已实现

新增零默认数据的宿主 identity／assignment 控制面：当前 head、append-only revision、幂等 command Receipt、服务端单调 revision、scope advisory lock 与 expectedRevision CAS。无 host 参数的 SECURITY DEFINER 目录 reader 以数据库 session_user 的角色名和 role OID 绑定固定宿主，只返回该宿主被显式分配的租户。

目录、runtime 与 Web 三类连接按数据库实际 authority、session user、role OID、组成员、特权和受保护表 owner 做隔离预检。受保护关系固定解析 public schema；缺失、重复、DSN 别名指向同一 principal、交叉继承、superuser、BYPASSRLS 或 owner 会话全部拒绝。CleanupOnlyOciDriver 只暴露隔离检查和精确清理入口，本切片没有调用 OCI。

## 验证

- 目录、连接、身份和 cleanup facade 专项：23 passed。
- 隔离 PostgreSQL 目录与角色专项：10 passed。
- extension-runtime 非数据库累计：303 passed、439 skipped。
- Outbox、恢复、配置、停用、生命周期与目录邻接 PostgreSQL：109 passed、1 skipped。
- 编译、Alembic 单 head 与差异检查：通过。
- 独立 Prime 多轮审查最终 PASS。

## 精确边界与下一交付

本检查点只标记 TRUSTED_DIRECTORY_AND_DATABASE_IDENTITY_PREFLIGHT_GREEN，不标记 production worker factory green。尚未实现真实 GenerationDrainReader、缺依赖零访问 INACTIVE 选择、空目录一次只读后 INACTIVE、生产 worker 构造和 main.py 启动接线。

下一交付先实现代次在途账本与 drain reader，再实现全依赖选择器；进程重建、旧 attempt 收敛与终态 ACK 使用隔离 PostgreSQL 联合反证。
