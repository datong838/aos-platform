# 实际DataPage连接配置增量

基线a625f7bc。路由核查发现旧DataSourceCreatePage未挂载，/data/sources/new redirect到DataPage；本轮旧页自有修改已全部撤回。实际DataPage补SSH主机/用户/密码，jdbc-mysql-ssh创建发送规范config，稳定自动id，保存版本用于后续CAS，GET确认版本后POST精确探针，成功显示发现表与尚未同步。移除实际页原“不落明文Vault”不实文案，未宣称加密存储。其他metadata创建流程保留。

helper三测试通过（字段过滤/数字端口、id失败不伪造、探针版本漂移拒绝）；TypeScript全项目--noEmit通过。之前41项包含未挂载旧页，不能作为DataPage交互验收。初次测试缺node，改用已安装bundled Node后执行。git diff --check通过。

浏览器实际打开127.0.0.1:8434/data?create=1&connector=jdbc-mysql-ssh，页面标题数据源管理，显示实际4步骤创建流程与已安装MySQL SSH卡片；仅核查首屏可达，未点击提交或填写真实凭据，未验证后续屏及保存探针端到端。后端API未重载，本轮无真实源/模型调用。

已知待处理：SSH端口当前22固定需提供输入；未知提交结果的版本恢复/重读交互需补齐；runtimeMode的agent/worker选择与本机探针语义应明确限制；配置编辑后旧探针展示需失效；完整组件交互测试、HTTP/PG锁、权限及真实接入仍待完成。因此不是向导或首链完整验收。不push，230 L0挂起。
