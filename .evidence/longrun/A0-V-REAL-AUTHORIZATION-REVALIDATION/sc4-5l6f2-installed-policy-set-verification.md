# SC4-5l6f2 当前安装六策略集合验证

基线`82086dfd`，功能提交`0c07989a`。按`snapshot-resume-design.md`新增`AnalysisSnapshotPolicySetOwner`，并在原`PipelineSnapshotGroupPolicyOwner`内抽取共享当前release解析及Registry artifact exact ref构造。固定六个标准策略路径均从原group当前安装的active baseline、published Registry记录、签名指纹、release evidence、manifest exports和artifact digest解析；调用方不再提供路径、版本或hash。六文档在同一完整group守卫内按relationship、quality、cohort、fact quality、business facts、readiness顺序编译并交叉绑定，消费后重新解析比较。没有读取candidate目录、商城源、确认Outbox、生成Evidence或恢复Run。

有效Red使用18432隔离PG与仓库虚拟环境，模块缺失导致collection `ModuleNotFoundError`。首次实现运行进入真实Owner后暴露测试连接未处于显式事务，修正测试；第二次暴露fixture当前身份不是`aos_runtime`，补回原角色与双租户GUC，未修改产品权限。专项最终7 passed/32.89s，覆盖正向六exact refs、artifact缺失/错digest、非导出、当前安装撤换、发布拒绝及回调中内容漂移。相邻单策略Owner和六编译器115 passed/3.87s；静态编译与`git diff --check`通过。一次回归命令遗漏DSN后默认5433拒绝连接，使用既定`AOS_DATABASE_URL=postgresql://postgres@127.0.0.1:18432/postgres`串行重跑通过，没有添加后门或放宽失败关闭规则。

专项仍使用私有完整PG和明确named安装发布/策略资产边界，不代表1.22.0已真实build/sign/publish/install，也未验证真实商城、Provider、经营建议或八工作台。下一波SC4-5l6f3将l6f1路由与本集合接入固定协调器，逐段调用原完整组、Evidence、Fulfillment和统一Resume Owners，并实现Receipt优先重放、未知结果不重发及Outbox确认边界。
