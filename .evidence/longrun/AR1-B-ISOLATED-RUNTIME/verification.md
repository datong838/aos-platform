# AR1-b 隔离注册底座交付核验

2026-09-05；m1；基线 AOS-000508 / ef5dcab2；Task AR1-B-ISOLATED-RUNTIME。

范围：1 MiB 长度帧、严格序号与信封、固定 OCI 隔离参数、镜像索引/缓存摘要匹配、注册描述对齐、Python SDK 包导入。注册阶段全部业务 ports 关闭，不产生安装 binding。AR1-c 负责当前签名/trust/eval/exact lock、持久 operation/未决清理日志与准入联接；本包不能作为业务运行入口。

真实环境：专用 colima-aos-extension（userns、seccomp），不重启或修改 Docker Desktop。固定 Moby seccomp 默认拒绝策略收紧 mount/ptrace/mknod 等；源码 blob 与许可见 SECCOMP-NOTICE.md。VOLUME 镜像拒绝，healthcheck 禁用。短寿命容器按唯一 owner 精确回收。create 超时无法确定 daemon 终态时保留 CleanupUncertainError 的 context/name/owner，不宣称已回收；取消与未决组合不能吞引用。

真实 OCI 8 项通过：注册及映射、非法输出、stdout 超限、stderr 超限、实际 SDK 相对导入、三类 syscall 拒绝、取消回收、15 秒超时回收。另模拟创建延迟/未出现与连续取消。

回归：精确清单209 passed（25.34s），随后追加取消+未决组合测试，最终结果以执行摘要为准。此前扩大 asset_registry 目录运行934 passed（79.78s）包含开发数据库临时 m2_w4 schema 测试；不是无数据库写入。fixture finally 删除自身随机 schema，随后只读核对 remaining_m2_test_schemas=0。此次范围偏大已披露；后续仅使用精确文件清单。

6 条已有 Pydantic 告警；退出 JDBC logger closed-stream 错误仍存在，缓存0/0，pytest退出0。不声称全仓无告警。没有真实业务数据修改、Provider调用、外部发布。本波未改UI，浏览器N/A；不以此替代后续页面验收。

Prime 增量审查指出并修复镜像隐含行为、SDK导入、创建竞态与取消组合；最终回读见 Delivery。业务闭环新增0。下一波 AR1-c 生命周期、持久权威、安全存储与签名联合准入。
