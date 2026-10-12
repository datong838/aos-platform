# 私密producer连接入口验收

新增默认off私密配置入口，保护文件校验提取自原writer，不重复实现。原wrapper仍同schema/role/错误消息及one-role约束。新schema只选择finisher用途，原生身份检查仍要求两个精确角色。已验证连接事务回IDLE后yield；caller必须显式commit，finally只close，未提交退出不会被上下文隐式commit。连接/身份错误不输出DSN，无runtime/superuser fallback，无自动retry/未知操作重发。

新模块缺失产生collection RED；39native专项通过后增加旧loader五负门及连接→完整终结两条集成，最终103专项/相邻PASS0skip、7既有warnings（15.18s）。真实隔离PG新LOGIN/角色，坏文件在connect前拒绝；原writer格式正向及权限/schema/role/duplicate/symlink负向保留，原nativeone-role检查也仍通过。完整签名终结经私密connector，独立读连接确认提交前不见新状态，显式commit后Run/Event/Receipt/Report/Proof/intent齐全；不commit关闭后全不变。

测试仅标准UUID完整实验DB/18431，临时测试LOGIN/finisher/私密测试配置文件。PG实验trust连接不是正式SCRAM/OIDC认证；未配置实际凭证、正式账号、权限迁移或公开路由。此connector只提供独立DB连接，不能代替Scope/Owner/预算/审批/签名/currentness或真实Target/Judge准入。原Goal、全恢复/八台自然首链未验收。

方案/代码复核一致，旧身份文件读取逻辑只参数提取，旧identity verifier、writer连接管理和权限均未更改。无页面改动无需浏览器检查；新增API代码需要最新冻结候选。保持22项用户改动，不push，不改真库/服务。
