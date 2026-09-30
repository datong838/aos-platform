# W5CB4 BG00ci｜当前正式 OIDC 与 checker 来源只读对账方案

依据231/231-5、BG00ch正式外部身份门。当前API仍旧owner，受限服务未切换；本波只读判断当前实例是否具备外部JWKS、issuer/audience、栖月汇组织成员及独立checker来源，不以开发账号或克隆正例补缺。

1. 只读检查当前API启动环境、`.env` 与私有正式配置是否有外部OIDC键（只输出存在性、URL scheme/host，绝不输出密钥/token），核 HTTPS/正式域名与JWKS可校验来源；无配置精确记录 `EXTERNAL_OIDC_CONFIG_REQUIRED`。
2. 当前权威卷只读核 `org-org/dev-project` workspace、身份/成员/权限目录和网络Proposal/Event/Receipt行数；`dev-org`仅canary读，禁止写；不读取商城源/用户隐私明细。
3. 比对已签名bundle、当前安装及网络Action元数据与正式maker/checker合同。若缺真实第二人或外部IdP，当前实例继续禁入，同时转BG00cj网络Event签发者数据库门的独立代码/克隆工作。
4. 证据、D-waves、上下文与m1精确提交；不切换当前API/数据库角色，不启Host/worker/Provider，不重放旧Run。
