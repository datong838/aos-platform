# W5c8v｜停止 VM 磁盘只读容器自启策略取证

## 上位与危险边界

承接 W5c8u `m1@2192c91e`/AOS-000683。8080 launchd 已精确 bootout，8080/18181 无监听；真实 `aos-extension` VM 仍停止。启动真实 VM 前必须知道 Docker 容器 restart policy，不能启动后再看。真实 VM 原始磁盘位于 `/Users/ddt/.colima/_lima/colima-aos-extension/disk`，包含数据库卷/可能的敏感数据；本波**只允许隔离测试 VM 从停止磁盘只读挂载并读取 Docker 容器元数据的 `RestartPolicy.Name`、容器名/镜像名的最小白名单**，严禁读取 DB volume、Mall 源或原始 config 环境变量。

## 步骤与文件级清单

- 先只读核实真实 VM stopped、磁盘是 regular file、路径/设备/inode/大小、测试 VM 运行且工具支持 `losetup --read-only` 与 `mount -o ro,noload`；若没有稳定的只读隔离路径，STOP，不安装新驱动、不启动真 VM。
- 在测试 VM 中用专用临时目录与只读 loop device 映射真实磁盘，确认 `RO=1` 后只读挂载 Linux 分区（`ro,noload`）；只执行明确定位的 Docker `hostconfig.json`/`config.v2.json` 白名单提取，不遍历数据库卷，不输出文件全文、Env、DSN、Mounts 或容器日志。只回报各容器匿名标识和 restart policy 是否可能自启；未知映射视为风险。
- 无论成功/失败必须卸载专用挂载点、detach 精确 loop device，检查真实 VM/8080 状态不变。任何权限拒绝、文件系统需恢复、元数据不全、设备无法清理即 STOP 并保留边界，不用可写挂载/修复命令。
- 只新增 audit/verification 文件，不改生产代码/配置；证据不得含凭据或源数据。如果证明全部容器仅 DB 且 restart=no，也只是下一波制定 DB-only start/纯 HTTP 读回计划的候选，不在本波启动真 VM。

## 九步

1. 复习 W5c8u/AT 与现时 VM/端口/磁盘。
2. 本方案提交。
3. 只读工具/路径/权限预检。
4. 可行时最小只读离线挂载与白名单提取；否则 STOP。
5. 卸载/设备/VM/端口回读。
6. 无业务 UI，8080 暂不可用如实记录。
7. 审计证据范围、输出脱敏和失败关闭。
8. verification/m1/D-waves/AOS CAS/Prime。
9. 自动 W5c8w：依据 policy 结果制定安全恢复顺序或替代取证；仍不自动迁真库/回填/ACK。

230 L0 挂起、商城源不读、dev-org 零 canary、unknown 不重发/不手工 `run_definition`、不 push。
