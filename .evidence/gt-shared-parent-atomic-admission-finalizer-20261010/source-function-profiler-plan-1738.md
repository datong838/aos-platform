# 原始核验函数级真实耗时测量

使用231、原联合方案3/11.3、工程交付Skill。当前AOS-001738/同线程Main Task与Support Task均活跃；上一轮为有效进展，根因未归属。本轮先验证观测工具，再对全原链创建一次全新Source/真实独立审批/完整调用的诊断尝试。不会重发旧attempt；期限不延长，Source正文和原生产核验代码不变。

文件目录：仅 `.evidence/gt-shared-parent-atomic-admission-finalizer-20261010/`，新增本计划、mechanics证据及 `source-profiler-native-1738-r1/` 诊断runner与原fixture副本。产品代码无改动。

指定隔离PG：cluster7694680278363095064，5441，Docker lab命名卷不变；正式库/Host/worker/Provider不参与。首次机制检查仅在同一admin事务内GRANT SET ON PARAMETER track_functions给当前隔离occupation角色，SET ROLE到该角色，SET LOCAL track_functions=all，执行原纯canonical函数并查看pg_stat_xact_user_functions，最后ROLLBACK；精确角色ACL应回原样。此检查不作为SCRAM/Source正向。

原链诊断：串行，无第二写者；暂时GRANT仅该SET参数权限（无表/函数/业务权限增加），连接仍真实occupation SCRAM，不冒充session_user；在连接任何事务前设置本会话track_functions=all。每次成功的test_owned外层调用之后只读同事务pg_stat_xact_user_functions，保存schema/function/calls/total/self time累计量，禁止记录参数、正文、凭证、查询或密钥。没有修改函数/触发器/源码来插桩。错误终止仍算失败，即使某组件已返回；原fixture清理与角色NOLOGIN恢复照常。runner finally精确REVOKE临时SET权限并回读pg_parameter_acl与原始字节一致；故障未知结果先只读对账，不能盲目重跑。

验收只证明诊断与归因：原DDL/原Source算法仍精确；观测产生嵌套函数真实calls/total/self量；全链可能仍期限RED，不把全链退化到单一函数来宣称通过。根据函数自耗时/原调用层数再决定最小优化，保留锁与等待后的全权威时限复核；禁生产参数变更或缓存历史授权。

## 真实测量后的只读归因复核
已知r2组件通过且whole期限RED，先在该保留库SER READ ONLY、SET LOCAL ROLE aos_capacity_publication_owner，独立调用不读业务数据、不加锁、不认证或发布Source的原require_original_fact_boundary；对jit on/off各3次测量并核body hash，退出恢复本会话参数。目的是区分内部规划选项与实际全schema权限扫描成本，不安装函数、不改变原SQL、不把该窄检查当Source/完整准入通过。证据只记录时间与函数hash。
