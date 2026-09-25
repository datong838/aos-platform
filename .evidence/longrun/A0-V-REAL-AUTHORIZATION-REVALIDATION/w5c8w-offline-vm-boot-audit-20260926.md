# W5c8w｜真实 VM OS 自启动与宿主作业离线审计

## 只读事实

真实 `aos-extension` 全程 stopped，8080/18181 无监听；在独立测试 VM 中对 OS `disk` 建 `--read-only --partscan` loop（`RO=1`），挂载 `ro,noload`（回显 `ro,relatime,norecovery`）。仅检查 `/etc/systemd/system` 启用 symlink/自定义 unit 文件名、`/etc/cron.d` 与 cloud-init 文本配置是否包含 `docker run/start`、`podman run/start`、AOS worker/Postgres start 模式；无匹配文件名。`/etc/crontab` 与 `/var/spool/cron` 在此镜像不存在；未把不存在视为系统完全无调度。

启用 symlink 中有系统 `docker.service`、`docker.socket`、`containerd.service`、`lima-guestagent.service`，没有名为 AOS/Postgres 的自定义 enabled unit。自定义普通文件限 `docker.service.d/docker.conf`、`user@.service.d/lima.conf`、`lima-guestagent.service`；其中 Docker override/guestagent 未见显式 `docker run/start` 命令。Colima profile `provision=null`、`autoActivate=false`。W5c8v 数据盘所见三个现存 Docker 容器均 postgres 镜像且 restart=`no`；组合证据可用于**下一波受控 VM-only 启动候选**，不能保证所有未知 guestagent 交互无 effect。

宿主 `launchctl list` 仍有 Prime safe、Web 8434、memory-health 等 AOS 作业；8080 job 已 bootout。不能仅凭 job 名字断言它们对数据库无作用；但 VM-only 启动不应自动运行 DB 容器，仍需启动瞬时重新检查 `docker ps`/端口且禁止手工启动 Postgres、迁移、Worker。

## 清理与剩余门

OS mount/loop 精确卸载/解绑；测试 VM `losetup -l` 空，真实 VM stopped，8080/18181 free；OS disk inode/size/mtime 仍 `33532558`/`21474836480`/`2026-09-25 23:55:22`。未打印 unit/cron 原文、环境/凭据或数据库内容。

下一波只能先计划 VM-only profile start（不启任何容器），必须新鲜回读 launchd/端口、Docker metadata/OS 条件；若启动后任一 DB/worker 容器意外 running，立即 STOP/冻结，不能继续迁移或尝试运行定义。原 12 Run/Receipt 当前状态仍未知，真库读回另门。
