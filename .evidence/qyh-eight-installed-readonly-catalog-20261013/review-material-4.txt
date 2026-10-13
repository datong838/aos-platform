# 栖月汇八工作台已安装资产只读查看恢复

Rules：用户AGENTS、仓库AGENTS、231、AOS工程交付；原八页与数据保持。用户已授权安装恢复与页面查看。

产品与技术依据：当前ACTIVE5真实签名四包具有八模块，旧目录legacy过滤与runtime-ready目录分别排除；原Host支持所有八页只读展示。独立GET已安装只读目录只恢复查看，不授Source读、消费、运行权限。

文件计划：
- services/aos-api/aos_api/ecommerce_installed_readonly_catalog.py：复用原Registry/Installation读取与原模块完整性投影；服务端精确选定installation，scope固定；真实roles/markings仍检查；每项强制disabled及只读禁入解释。无默认安装选择、无硬编码菜单。
- services/aos-api/tests/asset_registry/test_ecommerce_installed_readonly_catalog.py：真实保留签名资产fixture，安装选择/tenant/角色/撤回/内容漂移/始终不授运行反例。
- services/aos-api/aos_api/routers/ecommerce_workshop.py：独立只读GET，不改原业务CatalogDependency或业务门。默认未配置返回空；配置仅服务器端。
- apps/web/src/api/ecommerceWorkshop/client.ts：旧目录为空才读取独立已安装只读目录；原parser和原React页不变。

施工：专项RED→最小实现→原catalog/runtime相邻→路由与客户端测试→只读原PG验证→独立冻结评审→最新API/Web受控接线→真实登录SPA八路由验收及canary。未完成的环节保持待验收。安装撤回/替换每次重新读，不能缓存旧安装。

风险：只读展示不能当正式首链；不放宽legacy/runtime谓词，不伪造UI session。服务配置要求readonly数据库及本机management身份，公开工作台业务动作仍原门禁。
