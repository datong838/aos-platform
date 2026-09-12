# 已安装资产到读取规格验证

2026-09-12，基线765a06be。新增纯函数derive_mapping_read_spec；实际P01资产导出ns_site、Shop、site_id主键、site_id=1过滤及11个明确字段，不含site_tel。读取规格冻结，不带批准状态，不创建SourceSelectionRevision，不发源查询。

先红：模块不存在；实现后新增20项与关联查询/适配器共45项通过。评审补充MySQL列名大小写等价，两项拒绝测试先出现2 failed/20 passed，再以casefold判定重复列及禁止列，最终47 passed，3.92秒，7项既有警告。覆盖不一致Schema、缺策略/范围、禁止字段、错误字段类型、空/重复/越界列、增量模式拒绝；输入后改不改变冻结规格。AR2 ar2-7闭包1792/158/93，五类错误为空，diff检查通过。

08:03:53Z只读取得active@5安装锁中platform.ecommerce.niushop@1.3.0，核对published注册记录及三个文件digest/size；ManifestLoader实际验证文件字节。source-selection-installed-assets-preflight.json记录结果。08:09:29Z新解释器读取同摘要文件得到一致P01规格，见source-selection-p01-derived-spec.json。无业务源行读取。冻结Schema没有实时列类型，不得将该结果当成实时Schema验证。

生产CurrentRuntimeReleaseArtifacts拒绝诊断连接的非aos_runtime身份是正确保护，本波未改角色/权限。诊断文件核验只用于审阅已登记资产，不替代执行时的运行身份、安装、当前配置和数据授权。继承的aos_api包初始化会创建app并初始化日志；纯函数自身不访问数据库或网络，本波没有启动新服务。

08:00:21Z另一次只读连续性观察：三个容器running，8209.9秒、135次续租，binding ready/enabled/unfenced@4，canary安装0。证据source-selection-preflight-continuity.json。运行连续性不等于经营首链。

下一波：按source-selection-owner-plan.md补齐持久来源选择、当前权限/配置及版本重验，再将有效控制接入正式ScheduleRun/Ingress。P01仍禁用，未宣称实际同步、八工作台业务通过或发布就绪。m1串行、不push，230 L0挂起。
