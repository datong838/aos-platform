# 正式容量 Source 签发请求与外部身份入口检查点

基线 m1 3bfa87c9 / AOS-001351；ACTIVE gt-provider-capacity-source-20261005范围内施工。本检查点不关闭fullSource任务，也不建立正式供应商/账户/容量发行。

issuer-entry-red.log：37failed14.14s，新Command/Binding/入口缺类或缺模块。最小实现后issuer-entry-green.log：原candidate33+入口37合计70passed14.36s。issuer-entry-adjacent.log：契约70、producer、SourceAction26、原NetworkIssuerAuth相邻合计118passed58.99s。compileall三个文件和代码精确diff通过；无页面改动，浏览器不适用。原pytest日志原字节保留，失败输出的尾空格不作为业务问题。

Command严格positiveTenant/schemaVersion1/boundedSecretStr signedJWT/exactkey，ActionProposalrevision2/ActionApprovalEventrevision1/SupplierCapacityAttestationRevision/ProviderCapacitySourcePolicyRevision四refs。未知权限/actor/roles/verified/容量数字/账户ID/执行标记拒绝，旧LicensePolicy或EvidenceBundle不替代供应商证明/政策。重新解析model_copy嵌套改参，Binding覆盖protocol/tenant/authenticated maker/完整4refs，排除token/key，固定REQUEST_ONLY_NO_CAPACITY_NO_START。client ref存在不证明它可信或已批准。

真实本机隔离HTTPS JWKS+RSA证明JWT签名/issuer/audience/exp/subject/tenant检查与重复认证；错误签名/过期/受众/租户/发行方/缺subject拒绝，错误固定文本无token或原异常cause。配置反例在真实夹具上修改ALLOW_DEV/EXTERNAL_ONLY/JWKS URL/issuer/audience，拒绝前无JWKS请求。Principal/command子类不能代替命令。未调用真实OIDC服务或供应商，仅fixture验证协议。

受邀route_supervisor方案及代码只读复审无重大阻断；提醒后继必须重新认证原command并在同caller核DBfacts，不能复用返回Principal/Binding作为签发授权。此次受邀审查不代表后台自主报告/持续值班验收。

## 完整退出条件仍未完成

可信供应商Attestation及SourcePolicy真实来源、正式账户全域归一/双向唯一、独立私有数据库身份及ACL、issuer可用epoch reader、当前Owner与原同proposal唯一批准事件/所有Provider heads、原SERIAL真实COMMIT非执行签名Revision、consumer签名和当前性重验仍pending。共享occupation/旧占用零执行切换/预算容量一次Intent/transport/Usage/Report/Gate以及b90八facts完整COMMIT/API/ToolBinding/自然首链/八工作台/连续观察发布继续pending。

现入口只auth，不连接DB、不占attempt、不发行或激活真实Provider。当前142库无读取/迁移/重启，DB测试仅disposable5433，无Host/worker/现实Provider/Secret/商城源/旧12Run/manualrun_definition/230L0/未知重发/外部效果；m1单写/no push。
