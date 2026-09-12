# Niushop 1.4 隔离构建与恢复前置

2026-09-12，基线 8f2e4fef，m1 单人串行。沿已登记下一波，执行 scripts/build_niushop_snapshot_candidates.py，不新增业务代码。输出全新仓库外 state/niushop-1.4-build-v1 与 logs/niushop-1.4-build-v1.json；引擎固定 colima-aos-extension，临时构建 registry 端口 18436。检查已有构建保护、源码摘要、镜像摘要、依赖锁、SBOM、签名策略及实际 OCI session 注册/2048 次 heartbeat/释放；不降低既有资格条件。

构建只产生独立产物，资格签名为临时签名；不得将其作为正式可信注册包。保留旧发布目录和版本的内容摘要，不用重建产物覆盖已发布旧版本。不变更安装、源配置、审批、P01 启用、外部发布或 Provider。

执行前新发现：20:11:58+08 的原 Host v12 已退出。12:34:38Z 实测 CONTINUITY_FAILED；367 次历史续租，三容器 unavailable，binding unknown/desired enabled/实际 enabled false/fence true/revision 5，隔离 canary 安装仍零。对应系统电源记录有20:11:29 DarkWake及20:12:10 Sleep。先前11:29Z连续性证据仅代表当时；不再声称当前 Host 或三容器运行。API /v1/health 返回 ok，前端进程仍在。故障观察完整 JSON 位于仓库外 logs/niushop-1.4-before-build-host-observe.json，旧状态不改写。

租约失效不能加长 TTL 后复活。新版本构建后优先准备正式同范围 disable/恢复或卸载重装的确切方案，保留旧审批/配置/Receipt；生产数据不清理。启动入口还有凭据环境变量旧路径，需要在重启前复用已有受保护文件引用并补齐三身份读取；不能继续输出或复制明文到环境。该修改另起有测试的实现段，不能用本波构建完成代表恢复完成。

验证退出：实际 build 回执与文件摘要一致，实际 qualification 三成员通过并清理，旧源摘要不变，无安装/调用副作用。若失败保留失败回执，先查原因，不能重试覆盖同目录。恢复、正式发布、受控真实源读取与八场景仍未完成。230 L0 挂起，不 push。
