# W5c1 DS 的 Direct Successor 仅批准创建方案（2026-09-24）

## 现行前提

W5c0 `6460fecb` 只读确认：DS active/etag5，binding rev13/epoch7 disabled/fenced、8 个 operation 全终态、三 lease released、九路 legacy/fenced/无 gate、detach Receipt 完整、12 schedules off/active attempts0/canary0；原 `replacement_ref()` 精确接受。签名材料当前版本为 core 1.4.2、niushop 1.23.2、growth 1.10.2、operations 1.2.2；独立 Host/LivePreparedJob 均不存在。旧 12 selection 已过期，不能借用。

## 本波唯一授权与实现范围

仅按现有 `create_approved_first_installation` 和 InstallationService 原 Owner，用 DS 的不可变 `currentInstallationRef`、现行签名注册表快照与全新前缀创建一个新 installation 到 **approved**。不卸载 DS、不 prepare/verify/configure/enable 新安装、不切九路、不改 definition/schedules/selection、不读商城源、不运行业务。

新增 `scripts/a0v_w5c1_successor_approval.py` 与定向测试；先检查 exact DS、detach Receipt/hash、9/9 legacy、zero canary/attempt、当前版本签名材料与相同前缀的 command 数=0，冻结 0600 intent；之后只执行一次原 installer。installer 内部 composition→create→submit→approve 跨多个事务，任何异常/结果未知绝不整段重发，先按精确幂等键/Receipt 只读对账。不得借旧执行器里全库 `pg_dump` 备份，因为会读取商城源数据；本波只复用已存在的迁移/正式 Receipt 保障。创建后独立回读唯一新 installation approved/etag3、composition lock/currentInstallationRef、四包版本及签名、DS/路由/调度未动、canary0，再写 verification、m1 commit。

## 停止条件与下一波

旧 DS 身份/Receipt/九路状态漂移、签名不完整、prefix 已被占用、任一中间命令未知、或创建结果不是唯一 approved，立即停止写并只读对账。W5c1 完成后 W5c2 才可依 predecessor drain 与新 approved Receipt 正式卸载 DS，启动唯一独立 Host 连续 prepare/verify；Host 中断走既有 preparation-reset/direct successor，不复活 released lease。
