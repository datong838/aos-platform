# 实际构建与独立回读

原独立profile实际build exit0/BUILD_GREEN，输出位于合同固定aos-recovery路径。三runtime镜像完成实际无网络构建、本机只读fixture registry精确拉取；输出全部内容hash、SDK/依赖、四bundle release contentHash由原builder记录。原库/卷、正式Registry不写。

原qualification exit0/QUALIFICATION_GREEN：原ManifestLoader/ReleasePolicy接受新的临时测试签名，resolver实际解析core1.4.3/platform1.23.0/Growth1.13.0/operations1.2.0；8模块、3真实OCI runtime registration/session（每个2048 heartbeat）、Growth analyst单个fixture只读probe、七类签名篡改拒绝。Session cleanup released；临时签名不持久化，不使用正式签名身份。当前Host/worker/Provider不启动。这是隔离运行资格证据，probe明确qualification-fixture-only，不是真实业务验证。

第二独立进程回读：原build输出treeHash不变，三个localRef docker image inspect的configDigest精确匹配；旧core1.4.0 baseline hash不变、core1.4.3候选完整validation保持、输出无bundle.signature.json。build与qualification绑定同treeHash。详见independent-readback.json及原两receipt。

风险与未完成：临时Root不能作正式发布身份，旧Registry同版本冲突不可覆盖；正式签名/publish/configure/部署尚未执行，预算/权限/新配置不继承旧expired权。栖月汇名字、实际八页面与自然首链仍pending。下一项：准备独立恢复的正式签名输入合同与HTTP入口门；签名、Registry写、正式库连接切换须按既有正式权限门核验，所有旧库/卷/备份保留。
