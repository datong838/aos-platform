# 新安装四来源配置与受控启用

目标 e42e042b-1fe7-4cfa-bb83-469ff256081d，当前 Host v9 的独立 generation；职责计划已通过六角色就绪门冻结。

新增 scripts/a0v_ecommerce_1_7_configure.py。仅本地 aos_meta_head、正租户、已知安装；复用已有独立 runtime 身份，通过正常租户事务与 CurrentFourSourceConfigurationAuthorization 读取职责、数据分类、BudgetRevision、RuntimePolicy，以及策略所引用 network/egress/quota/BudgetPolicy 的 exact current 版本和时效。禁止用目录文件内容或旧 ready 标签替代本库来源。

阶段：preflight（纯读取完整四来源授权并回读现场）→append_configuration 保存不可变配置、原 CAS 和幂等键→RuntimeConfigurationService.request configure→观察 Host 成功→同一 committed configRef 请求 enable→观察 dispatch/绑定与实际接入，不直接改状态。异常/未知请求先观察，不重复提交。配置数据范围继承当前 public catalog 分类策略，具体经营查询还需各自 SourceReadiness。

目录、来源和代际漂移拒绝；操作与证据原子保存仓库外 state，每一步落证据提交。保持旧制品和已卸载安装历史。当前启用只授权领域运行 API 接线，具体模型、业务动作、评审和外发仍由原能力治理逐次判断。

实际预检确认 web identity 仅供运行身份分离检查，不能 SET ROLE aos_runtime；配置表及四来源读者明确属于 aos_runtime。保持 Web 身份无新增授权，执行器使用已有独立 runtime_worker_connection，并按正式租户事务应用 scope；此路径仅写控制请求/不可变配置，Host 仍是资源执行与 generation 续租单写者。不向 web 角色补 runtime 权限。

安装状态从 bundle_installation_revision 的 current_revision 读取，CAS 从 bundle_installation 读取，保持租户及 installation_pk 精确关联。预检字段错误发生在任何配置写入之前。
