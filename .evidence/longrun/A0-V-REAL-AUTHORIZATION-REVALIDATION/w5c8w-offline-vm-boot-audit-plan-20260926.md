# W5c8w｜离线 VM 启动机制与宿主 AOS 作业只读审计

## 上位边界

承接 W5c8v `m1@b001b5c8`/AOS-000684：停止真实 VM 数据盘 3 个 Docker 容器均 restart=no；OS 盘尚未检查 systemd/cron/custom unit，宿主 8080 已 bootout、其它 AOS 作业存在。不得把 Docker policy 当整机零执行，也不启动真实 profile/真库。

## 精确路径与输出白名单

- 在独立测试 VM 中只读映射已停止的真实 OS `disk`（同 W5c8v 的 `losetup --read-only`、RO=1、`mount -o ro,noload`），仅检查 `/etc/systemd/system` 与其 enable symlinks、`/etc/cron*`/spool 的**文件名和是否包含 Docker/Colima/AOS/Postgres 启动命令**；不要输出 unit/cron 原文、Environment、ExecStart 参数或路径外数据。Colima `provision=null` 另作旁证。
- 对宿主 `launchctl list` 仅列 AOS job label/PID 与 8080/18181；只读分类是否有另一个会自动启动 Runtime Host/worker 的进程。不能证明的 job 标 `UNKNOWN`，不靠名字推断无 effect。
- 无论发现什么，卸载/解绑精确只读挂载与 loop，回读真实 VM stopped、8080/18181 free 和磁盘 mtime/inode；失败不修盘、不写配置。
- 本波只新增 audit/verification，不修改生产代码/launchd，不启动真实 VM/DB、迁移、商城源读取、回填或 ACK。

## 九步

1. 复习 W5c8v/AT、当前 HEAD/VM/host jobs。
2. 本方案先提交。
3. 只读路径与工具/RO 预检。
4. 最小白名单离线 OS/宿主启动审计；未知即 STOP。
5. 卸载/设备/VM/端口/文件时间回读。
6. 8080 暂不可用，业务浏览器不填 GREEN。
7. 审计是否足以规划 DB-only profile 启动，不能则给精确下一波缺口。
8. verification/m1/D-waves/AOS CAS/Prime。
9. 自动 W5c8x：若 VM 启动机制无执行副作用，再制定 DB-only profile start 与单一 Postgres 容器读回计划；若有未知，先补隔离 guard，不冒险启真库。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
