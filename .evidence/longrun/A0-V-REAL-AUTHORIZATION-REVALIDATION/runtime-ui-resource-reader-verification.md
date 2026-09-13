# UQ5-B2a 可信签名页面读取核心

2026-09-13，m1基线e88cc76e，不push。

新增PublishedUiResourceReader：精确参数化Registry发布版本查询，当前ReleasePolicy/信任根验证，绑定记录唯一sourceRef与allowlist加载包，核对manifest/packageHash/signature、frontend manifestHash及唯一入口contentHash，读取有界UTF-8 HTML。返回前新事务再核发布证据；不读租户业务表，不提供任意文件访问。

测试采用真实临时包/Ed25519签名/ManifestLoader/ReleasePolicy；Registry连接与行是替身，不能算主库发布验证。15项新测试覆盖正常双校验、非法身份/路径/摘要、未声明HTML、篡改、软链接、替换签名、读取期间撤销、信任根不可用和重复记录。连同原加载器、发布策略、资源解析共81 passed，7项既有警告。

限制：尚未挂HTTP或实际部署；来源静态代码无业务身份。HTTP需显式配置资源和父页面origin、沙箱CSP、无网络能力、no-store、错误脱敏和重复参数拒绝。后继B2b直接承接，再B3真实后继包。
