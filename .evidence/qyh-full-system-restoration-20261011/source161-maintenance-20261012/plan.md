# 原栖月汇卷159→161维护方案
Rules：AGENTS.md、231、用户批准的全量栖月汇恢复。parent Task/Lease拥有此原卷维护，其他分支/原preview资源不动。
候选一：原卷独占维护及最新双备份、完整独立恢复、160/161逐步演练；候选二：正式OIDC/独立publisher接入，原配置路径待答。先一。
源精确CID84989681/卷aos-qyh-history159-prepared-data-20261011/cluster7695302940039200809/aos_meta_head159/647表；实验精确CID3fb59cb/卷aos-qyh-current159-exact-restore-20261012/network-none。当前四包fullschema原Store已完成候选协议验收，独立入口review格式失败不得绕过或称通过；它限制下一API正式接入，不给本维护追加假授权。
1. 原只读汇总clients/prepared/bindings与HBA解析；clients非0或prepared非0拒绝，不杀未知backend。维护前源完整647数据指纹、schema-owner-ACL、序列、角色组；私有0600保存原HBA。
2. 针对仅aos_meta_head前置local aos_app原维护通道，其余local/TCP全拒绝；reload非重启。实际TCP拒绝及维护通道成功、clients0/prepared0验证后，持续持有围栏直到全部迁移验证完成。
3. pg_dump最新custom两份0600校验相等；原新network-none实验DB完整事务restore，clone-only replica关闭业务触发器；原647指纹/完整schema-owner-ACL/序列/角色组匹配，失败不迁移原库。
4. 当前已提交冻结代码原Alembic离线SQL逐步159→160→161先新完整restore库演练，记录每步intent/terminal不重试未知结果。全646业务表/12序列/旧647ACL/RLS/trigger/defaultACL/角色组不变，三个新表为空、forcedRLS、runtime仅SELECT/writer窄列。
5. 只有这些真实门通过且窗口仍成立，才在同窗对原库精确执行同两SQL；异常先读schema/terminal对账，绝不自动重发。版本/650表/数据/ACL等原生专项及相邻比对后finally恢复原HBA精确字节、reload/解析及原API只读连通。
6. 无PG/API/Web重启（aos职责），不开Host/worker/Provider，不变binding/schedule/旧Run状态，不发布/安装包、不构造OIDC/publisher/Owner、不读商城、不手工Run、不push/删除卷备份。原管理API旧进程未重启，迁移成功也不宣称最新启动/八台/自然首链。
未知效果：O_EXCL源intent及每步intent、独立terminal、finally原HBA恢复结果；遇已存在意图只读对账。审阅器本次不消费失败输出。产品源码不改，具体实现只此目录维护执行器，先AST与方案/实际差异复核后执行。

## 预实施审阅修订（尚未执行源围栏）
首轮draft在HBA/源intent前比较角色失败：保留实验cluster40含前序160创建的aos_aip_eval_writer，真库159为39；无源副作用。独立clean Task已创建新network-none集群，39角色/12membership逐项真源匹配，旧实验保留。下一执行必须换新CID52cc28f30197cc4010bd0167139e849e239591d7d9c47023ebcb36ac06164e7c/cluster7695744911813242913/卷aos-qyh-source161-clean-maintenance-data-20261012。
代码审阅同时确认原a160明确新增NOLOGIN/NOINHERIT canonical writer角色，并给旧aip_eval_run新增SELECT及唯一双tenant读取policy；因此原draft“迁移后所有39角色/647 ACL完全无变化”的断言并不符合原方案。必须修成精确允许这三个声明变更，原39角色与12成员不变、其余646表ACL/policy/所有old触发器/defaultACL不变，再完整副本原生验证；不能忽略或泛化权限差异。当前maintain.py仅未通过预实施审阅的draft，禁止直接再执行；source version/HBA不变，下一波先修执行器核对新declaredrole与单Run读policy的原生精确结构。
