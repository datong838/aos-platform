# 原发行与签名安装当前基准复验

复用原s3o-w-h/k/n方案和已有product/test实现，没有重写原业务逻辑。在colima-aos-extension新qyh-source-writer-lab-20261011临时数据容器（loopback18432、不同cluster、无权威volume）运行固定端口受限发行/Source预检原测试：36 passed、8 xfailed、exit0。8个xfail明确是普通runtime可伪造Plan/Receipt的未闭合发行安全条件，未计通过。

再以已有真实本地签名回执 .aos-growth-113-signing-receipt-20261002-r1.json 运行原完整schema安装测试：1 passed、exit0、15.22s。原fixture自行校验签名树/hash/trust root/原ReleasePolicy，创建并清理一次性aos_test_*_ti4_test数据库，并测试原签名安装/受限Plan create、revise、幂等、冲突、错误版本、回滚、跨租户及原BI/OCI后续流程。该测试本身依赖临时测试主体/预算和隔离资源，不证明当前正式Publisher/Owner或自然经营首链。原successor和Content仍有真实前置条件不足的失败封闭路径，未当正向成功。

标准迁移引用aos_app，专用新lab原本仅有postgres；按原方案精确增加NOLOGIN/non-super/NOINHERIT aos_app供原迁移授权，未向当前库申请或创建业务身份。迁移产生的30个NOLOGIN逻辑角色合理保留在独立lab，所有临时issuer LOGIN已清理，非默认用户测试数据库0，OCI owner标签残留0。首次独立检查错误地预期只有3角色，已纠正为保留原迁移角色并实测canlogin/super/BYPASS均false，不为制造0残留删原逻辑角色。

独立Source647表指纹与上波完整恢复r2一致、原六metadata hash精确一致，Source权限0变化。HEAD绑定b10afb9d8，执行是当前工作树原代码（用户未交付改动未覆盖），Python源码合成hash是执行后记录，不宣称预冻结制品复核。API/Web/Host/Provider配置未改变。本波没有产品改动，现有八页面仍禁入，浏览器不重复计通过。

验证范围与方案自洽：专用PG容器创建intent只执行一次，端口空闲前检/PID1最终postgres/实际container挂载与loopback/cluster/readback均核验；stdout日志及退出码真实保留，秘密scan和AST通过。目标仅为恢复原测试基准和识别可复用实现，不替代正式角色/凭据与运行迁移。

下一波沿原完整Source Writer合同：使用固定最小不可登录逻辑issuer、精确LOGIN绑定和对应原Store same-caller事务，补齐generic/BI/successor/Content/Contract连接，不授issuer runtime成员、Owner或BYPASS；先在该隔离lab原全链上证明兼容和8个安全xfail对应条件，再完整备份恢复克隆切换，当前库ACL保持。正式publisher与当前预算、八配置、Host、八页面、自然首链独立未验收。Task和Goal保持ACTIVE。
