# N8 当前运行时工作台目录

基线 cc21830d。承接 routed-ui 技术方案，不开放旧目录，不把候选安装解释成执行许可。

文件：services/aos-api/aos_api/ecommerce_workshop_catalog.py 提取共用只读候选查询，旧 read_active_bundles 继续只读 legacy eligible；新增明确 read_runtime_candidate_bundles 分支。新 ecommerce_runtime_workshop_catalog.py 复用现有签名模块投影与角色/marking 校验，再通过 RuntimeViewReader 按每个精确 route 验证 ready/current revision、generation/epoch 和非空签名前端 UI。新模块不调用旧业务读取器，不放开 legacy_content_predicate。

候选读取保留同一 REPEATABLE READ READ ONLY 事务、Scope 和先 replacement graph 后 marking 的规则。runtime 候选必须确有 runtime bundle，完整 Registry/lock 校验不能省略；invalid legacy=false 不等于 runtime 已授权。目录输出为单独 runtime envelope（模块元数据+当前运行身份+签名资源信息），不携带持久执行授权。无前端、停用、封锁、revision 不一致、路由不属于资源均过滤；异常整体拒绝，不回退旧页面。

随后 control_wiring 用同一受控 loader/RuntimeView 接独立只读目录接口，前端宿主仅对 runtime envelope 挂载 ExtensionHost；旧页面分支不复用新目录。跨租户/旧请求/目录过期时卸载 iframe，绝不保留可执行旧会话。前端包构建、bridge read/command 当前权限及自然经营链另行完成。

验证分层：旧目录与 replacement/marking 回归；runtime 候选分类及签名元数据；当前绑定/资源过滤；接口租户隔离；主库当前预期空（尚无 frontend），直到正式新包交付才可出现入口。所有新增候选/测试都不是业务链完成证据。

## 依赖边界复核后的收敛

清册将旧 ecommerce_workshop_catalog.py 归为迁移节点，因此新宿主不能依赖其领域投影来完成运行目录。调整为将既有通用 Registry/Installation 候选与替换图、锁/制品校验机械提取到 asset_registry/workshop_catalog_source.py，旧目录从共享模块导入以保持行为；新 runtime 目录直接消费共享 source、ManifestLoader 返回的 WorkshopModuleContribution，以及 RuntimeView。不调用旧电商依赖就绪计算，不创建同一查询/替换图第二套实现。共享模块以明确宿主只读职责登记闭包，不扩大整类允许调用范围。
