# W5c8v｜停止 VM 磁盘离线只读容器策略审计

## 精确范围

真实 `aos-extension` 自始至终 stopped；8080/18181 均无监听。通过运行中的独立 `aos-a0v-test-only` VM，先核实真实 OS `disk` 和 `datadisk` 都是 20 GiB regular file，再分别以 `losetup --read-only --partscan` 映射，`lsblk RO=1`，`mount -t ext4 -o ro,noload`（回显 `ro,relatime,norecovery`）。OS 磁盘 Docker containers 目录为空，已立即卸载/解绑；数据磁盘仅打开 Docker `containers/<id>/hostconfig.json` 和 `config.v2.json`，程序只输出白名单 `Name`、`Config.Image`、`RestartPolicy.Name`，未输出 Env/DSN/Mounts/日志，未进入任何 `volumes` 或数据库目录，也未读取商城源数据。

## 白名单结果

数据磁盘 Docker metadata 中恰有 3 个容器目录，均解析完整：

| 容器 | 镜像 | RestartPolicy.Name |
| --- | --- | --- |
| `aos-a0v-recovery-pg` | `postgres:16-alpine` | `no` |
| `aos-ar1c-pg` | `postgres:16-alpine` | `no` |
| `aos-ar2-validation-20260909` | `postgres:16-alpine` | `no` |

这只证明**Docker 自身现存三个容器不会因 daemon 重启按 restart policy 自动启动**；不是 VM 内 systemd/cron/custom provisioning 零执行证明，也不是启真库、迁移、原 12 Run 读回、回填或 ACK 授权。

## 清理与停线

两个只读 mount/loop 均精确卸载/解绑，测试 VM `losetup -l` 空、无 `aos-w5c8v` 挂载；真实 VM 仍 stopped，8080/18181 无监听。`datadisk` inode/大小/修改时间保持 `33531503`/`21474836480`/`2026-09-25 23:43:09`。未安装驱动、未启 VM、未修复文件系统或写盘。

下一波需只读审查 VM OS 磁盘的自定义启动单元/Colima provision 与宿主 launchd/端口，证明 DB-only 启动计划；旧 8080 plist 的 Host/worker/Cron/迁移旗标依旧不安全，必须保持 bootout。真实 profile start 继续单独门禁。
