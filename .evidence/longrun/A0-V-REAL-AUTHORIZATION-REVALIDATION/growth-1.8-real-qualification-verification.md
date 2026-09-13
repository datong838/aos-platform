# UQ5-B3c 实际OCI构建与资格验证

2026-09-13，构建/资格代码HEAD 1b03336c，m1不push。

BUILD_GREEN，输出仓外.aos-recovery-20260913/state/growth-ui-1.8-build/candidates，树hash sha256:31aa95f0b132ca910df45cdf72a976dee052fa477bf51f7ec2fea5218b5cf06e。4包、3 runtime、8模块、13API；对比之前niushop1.5构建，core1.3/niushop1.5/operations-base1.2 contentHash均相同，只有新growth1.8新增。

QUALIFICATION_GREEN：真实隔离OCI、临时签名/发布策略/组合解析/镜像准入/Schema准入、7项签名篡改拒绝。core/niushop/growth分别精确注册1/2/24项，均2048心跳后released。growth同一会话只读探针1Case/1Run，resultHash sha256:a352f97d7fc23f2553442dba29276783f2eb2bc589b537940bd84c4ebacc7e4d，executionAllowed=false。fixture明确qualification-only，不是真实租户经营结果。

资源journal三份均released，Docker当前只剩原3个业务容器和原2个PG容器。Registry发布、安装修改、Provider调用和外部发布均0；原Host/主库不变。临时资格签名未持久化。

下一波：只追加growth1.8的永久签名新根与本地Registry记录，严格复核当前13版本旧根原字节；然后进入UQ6主库备份/迁移/原Host升级/真实安装读取。独立审批身份缺口仍不以fixture或角色伪造绕过。
