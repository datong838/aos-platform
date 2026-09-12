# Niushop 1.4 实际 OCI 构建资格

2026-09-12，源码基线 8f2e4fef。固定隔离引擎 colima-aos-extension，仓库外全新目录 state/niushop-1.4-build-v1。构建 BUILD_GREEN，资格 QUALIFICATION_GREEN；本目录归档两个原始回执 niushop-1.4-build-v1.json、niushop-1.4-qualification-v1.json。

组合为 domain 1.3.0 / niushop 1.4.0 / growth 1.7.0 / operations-base 1.2.0，8 模块、3 运行成员。三个真实 OCI session 精确注册，各 2048 次 heartbeat alive，最终 released。实际镜像索引、imageDigest、dependencyLock、SBOM、backend、schemaCompatibility、schemaRequirements 七类篡改拒绝。临时资格签名未持久化，无正式注册发布、安装修改、Provider 调用或外部发布。

12:38Z 使用项目 Python 3.11 重新计算输出树摘要 sha256:58f773aed1a8ba2946d685af14d7b0fb91b9cd4c1bee183a50df534ab2fac062 及全部 contentHashes，均与构建回执一致；旧 Niushop 1.3.0 源树摘要不变。Docker 复查只剩两份既有数据库，无遗留资格容器。新平台内容摘要 sha256:05dcca8fb3f28ef338f63118a753daabe91804aec2aa4cafc76756606735bad0。

过程偏差透明记录：Lease 最初用仓库外绝对路径登记被工具拒绝，后续同工具块的隔离 build 已启动；20:36:42 以既有构建入口的仓库相对路径补登记成功。没有借此扩大构建授权，也无安装/源数据操作。后续登记必须独立检查成功才启动动作。证据归档后一次只读摘要脚本误用系统 Python 3.9，因 datetime.UTC 导入失败；归档文件已写入，未重复覆盖，改用项目 Python 3.11 单独重算成功。两项偏差不算产品验证成功证据。

当前故障边界：niushop-1.4-host-interruption.json 记录原 Host 20:11:58 退出后的真实失败状态，367 次历史续租不能代替当前存活。API /v1/health 正常，原电商实例已 unknown/disabled/fenced、三资源不可用，真实经营首链尚未完成。不得把本次资格容器当业务运行恢复。

下一波优先重启前置：复用受保护凭据文件引用补齐 runtime/directory/web 三身份读取，移除独立 Host 对明文环境变量的复制，验证失败不回退、身份分离及现有运行路径兼容；之后走正式旧实例恢复与新包安装方案。新构建的其他旧版本产物不得覆盖既有发布版本。230 L0 挂起，不 push。
