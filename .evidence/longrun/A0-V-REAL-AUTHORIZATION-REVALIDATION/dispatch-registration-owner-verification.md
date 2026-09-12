# 登记Owner事务与历史读取切片验收

2026-09-13，基线b8ddb244。新增registration Owner与Receipt decoder，提取现有预检的当前安装/四来源部分；原空组预览行为保持。

- RED：Owner/decoder模块不存在，两测试模块收集失败。
- GREEN：Owner编排、Receipt防伪、预检及请求契约65 passed（4.87s）。7项既有警告和已有unsafe construct测试的序列化警告。
- 隔离PG通过触发器记录INSERT时pg_backend_pid/txid_current，和当前检查节点记录完全相同；检查时runtime、登记时maintainer，回读回到runtime；同请求重放同Receipt，不受空组条件误挡。
- 检查抛错、返回None/false/空值及回读校验失败均无路由残留；历史读取在runtime版本变化后仍要求当前权限，拒绝分支不返回记录，允许分支仅historical=true/executable=false。
- Receipt decoder核验canonical hash、行/payload双scope与身份、严格请求hash、固定九项fenced snapshot、actor和有时区时间；重算hash的伪造snapshot/请求/租户/执行标记仍拒绝。
- 06:46新代码独立进程调用真实主库的现有四来源预检，currentConfigurationValidated=true、authorityValidated=false、executable=false、businessWrites=0。未调用主库027函数。
- AR2清册1815扫描/158分类/93迁移，五类错误列表全空；diff检查通过。

明确限制：Owner隔离PG测试替换了当前权限检查节点，使用最小基础表和真实027/RLS/非特权双角色连接，仅证明事务编排；历史读取权限节点亦为编排替身。真实四来源单独预检通过，不代表“完整四来源+签名声明+维护身份+正式API”整链已验证。新Owner未挂API、未配置生产维护连接，API进程未重启，主库仍未迁移026/027。

自审：复用consumer_connection，独立idle连接在事务开始前设serializable并在退出恢复原隔离级别；无自动重试。当前检查结果必须明确成功且requestHash一致。只有在同事务核对数据库回执成功后才提交。历史读取独立当前角色/markings检查，不调用登记或切换，不恢复旧generation。

下一波：完整签名包九项声明资格、正式控制平面连接/HTTP接口及独立权限审查；补真实全依赖Owner验证，并接首次fenced exact切换与未激活撤销/卸载。上述门通过前不部署026/027、不把测试GREEN当作经营首链成功。
