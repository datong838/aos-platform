# 原67步历史迁移隔离演练

Rules: AGENTS、aos-engineering-delivery、231-4、已登记历史恢复D-wave；先方案再实现，产品代码不改。

候选名称恢复待授权；候选历史092→159隔离迁移已登记且baseline恢复完成，本轮选择后者。

固定历史恢复目标ccaaaa4655a86f0beba1bcbcce8891def8146abfd55b3561c5872be53791216e/networknone/noports/no sourcevolumes，原source仍只读。冻结当前m1 HEAD已提交services/aos-api完整tar到新独立只读代码卷，原tool image2376642...不拉取网络，全部文件SHA核验。脏工作树代码不进入执行器，不覆盖现有修改。

每步原Alembic93到159：单独短事务，实际Unixsocket/隔离cluster/数据库aos_meta_head/精确前版本/代码SHA验证；保留intent/terminal，退出0再独立psql读版本和原578表fingerprint（alembic_version例外）。任意旧行/schema引起数据变化必须记录精确差异并停该迁移动作，不能自动豁免。旧Run不执行，未接API/Host/worker/Provider。

不因超时或观察失效重发；重连先核版本/容器/未知结果，已提交步骤不得再执行。恢复target保留，备份保留，source前后指纹保持。此处是迁移兼容演练，不授当前正式恢复/数据库切换或运行权限。

首轮93在迁移import时缺fastapi，exit1；独立回读仍092，578原指纹核验后可新attempt。保留失败容器/日志；使用既有缓存纯Python wheels补充独立deps卷（fastapi/starlette/anyio/annotated_doc/idna/exceptiongroup，不替换原pydantic/native dependencies）。无网络下载，无原镜像修改；完整补充文件SHA在每步进程核验，r2容器名/intent独立。不重跑源码冻结或原93attempt。

117已提交后精确diff仅meta_object_type/meta_action_type各新增原迁移的一行，动作停止并保留；不是旧数据覆盖。复审原117/129/130/133/140/146/148显式元数据INSERT，冻结精确ID/六字段、源码SHA和版本阈值；逐步验证新增值逐字段等于原SQL、旧行过滤新增ID后count/hash完整相同，其余575旧表仍全指纹。除这些精确原迁移新增记录外任何差异仍拒绝，不豁免旧Run/安装/配置或业务行。r3从已提交117独立核对后仅118起接续，不重放117。

最终独立检查原先假设所有69新表为空，失败后只读调查发现151原迁移明确按历史proposal/withdrawal回填withdrawal_epoch。改为仅此表允许原SQL精确集合：双向EXCEPT逐行一致，其他68新表仍为空；不改任何库行。核冻结151源码SHA，源历史578表完整指纹、67terminal提交、旧安装active revision与binding/config均保持；不把历史active标记当运行权限。
