# 栖月汇恢复主线门禁核对

本轮回应用户“既有登录配置和独立发布身份接入做了吗”。二者尚未接入；不能将数据恢复或隔离实验报告成全系统恢复。

## 当前只读回读

当前 m1 HEAD ddd995bd69c20ec72f52c2b62a9635ce6dd56772；Goal active。恢复入口 preflight 实际成功：aos_meta_head@a0v_159，集群7695302940039200809，既有命名卷aos-qyh-history159-prepared-data-20261011；org-org显示栖月汇商贸有限公司，dev-project；647表、135安装、130配置、126绑定、0 enabled。8080/8434存在监听，18080没有监听。监听仅证明进程存在，不证明数据源或页面正确。原22个tracked改动不触碰。

## 门禁来源及适用范围

- 产品方案132明确保留非生产Dev登录，完整企业OIDC为另一登录路径。auth.py/oidc.py当前代码也支持两条路径。恢复脚本external-only限制是当前受限启动方案所选模式，不是所有产品模式都必须外部OIDC的证明。任何模式调整须先独立评审真实访问权限与数据库写入能力，不能直接启用dev当作正式Owner或发布者。
- scripts/a0v_qyh_restored_http.py的四个固定版本限制是此次“最新四包”恢复目标校验。它不能证明已有正式发布历史安装完全不可读，也不能伪造最新Registry状态。独立发布身份缺失仍限制新版本发布。
- ecommerce_runtime_workshop_catalog.py的实际可见性要求effectiveState=ready、binding enabled、operationFence=false及当前签名UI会话。这是产品真实门禁，不能仅删除启动脚本条件就声称八工作台恢复。现有绑定全部禁入，是必须继续核对配置及安装状态的真实限制。

## 下一实施方案（未执行代码修改）

先区分：租户与历史安装的管理展示、既有签名工作台可见性、正式业务执行。逐项沿原产品接口核对，不将缺少独立新包发布者扩大成所有管理页面都不能接回恢复卷，也不把管理展示改称正式工作台运行。

拟修改范围如需实施，仅限当前Task已登记的scripts/a0v_qyh_restored_http.py及services/aos-api/tests/extension_runtime/test_qyh_restored_http.py；先完善plan.md与具体用例，验证原认证/租户/签名/禁入不回退。产品目录或登录权限如确需新增逻辑，先登记对应文件级Task/Lease再编码。保留原发布职责分离和Host/worker/Provider授权门。未满足这些条件前不改启动参数、不开放绑定、不写生产发布状态。

既有电商开发、栖月汇历史安装与配置仍保留；原隔离验证只能证明对应逻辑，不能代替栖月汇实际八页验收。本轮未改代码、未重发发布、未重启服务、未改变长期Goal状态。

## 目录实测步骤

新增本Task范围内audit_workshop_routes.py，调用现有PostgresWorkshopCatalogSource的两条只读目录来源，通过现有有限LOGIN、aos_runtime及READ ONLY事务读取。仅输出安装ID、不可变版本、模块声明与目录分类，不输出业务payload或身份凭证。正向org-org/dev-project、零污染canary dev-org/dev-project各两次独立连接读回，摘要比对；不能绕过原租户RLS、replacement选择或legacy/runtime排除逻辑。前端路由接线另只读核对。当前步骤不启动服务、不改变正式绑定、不授业务权限。
