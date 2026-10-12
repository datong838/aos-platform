# 活跃 Source 演练资源的完整可恢复检查点

Rules：沿本已登记Source Task/Lease和用户批准隔离实现；唯一写者，先方案，未来仅本目录 resource_checkpoint.py 与独立clone维护；无当前库/服务/Goal/Owner变更。候选A为该真实资源检查点与内存释放，候选B为不需新PG资源的Source reader/锁代码分析。选择A准备，尚未执行stop；Task本身不收口、不设置paused/blocked。

当前native绑定 capacity clone bb9c8b1ab46af632af36ee89c9f2686f06ace9bbd803040ce44cab057968d486、cluster7695416748450308141、5个非模板库共403185243字节、0其他clients、0含已存凭据的LOGIN角色、无命名卷/tmpfs。此真实检查不代表原库凭据或业务权限。不能照搬命名卷stop流程：该数据必须完整归档后才能释放。

下一执行须再次核本Task合法Lease、精确CID/cluster/端口/无卷、全部5库目录/角色与原私密配置引用、无其他连接和足够256MiB读取余量。每库native READ ONLY repeatable snapshot、serial650表级原算法指纹（1MB work_mem、禁并行、5s statement_timeout），pg_dump完整schema/data/owner/ACL及所有globals --no-role-passwords，新private700文件600，两份SHA；除了pg_restore --list，还须pg_restore --file=/dev/null完整解码全部archive（不连接DB、不执行SQL、不输出原行）。源Lab角色仅0已存LOGIN凭据才允许无口令globals保留；若变化则拒绝且不读取/输出凭据。

目录/roles/序列及各库前后全表指纹无变化、archive完整解码和两份一致后保存独立checkpoint manifest，绑定Task/thread/repo/authority、精确资源及恢复命令/原bootstrap、全部数据和配置文件hash。必须明确未来新Role oid变化通过原维护门处理、私密身份文件仍保留、当前步骤没有业务执行。只读确认0clients后再独立freeze review（新鲜review Task必要时只持材料scope）及stop intent；没有完整恢复证据则保留限制，不能把文件SHA叫正式全库restore通过。停止tmpfs意味着只能从archive恢复实验数据；原clone容器和双备份保留、不删除现库卷、不修改旧Source业务结果、不重发任何已有unknown操作。
