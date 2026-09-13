# UQ4-A 受限结果查询

基线1ab80639，m1单写、不push、230 L0挂起。新增a0v_035只授专用API角色两个固定函数EXECUTE，不授队列表SELECT/DML。先取无业务结果的元数据，再由应用复核当前主体/markings、规范请求摘要、当前签名目录及exact target/dataScopes，通过后查询当前绑定下原主体的结果。结果状态、摘要、scope和固定失败码二次校验。

新增13项真实非超级PG查询验证；与6项完整迁移库ACL、13项入队回归合计32 passed/7已有warnings。成功结果可重复查询但Attempt总数仍1；未完成/未知失败不含业务结果；他人、负租户、未知请求、撤权、旧资源、旧binding、错误hash、超级账号和错误隔离级别均拒绝。资源拒绝发生在result函数之前。目录/baseline与OCI是已说明的测试替身，实际队列/Attempt/角色/事务/结果存储为PG。

首轮两项测试装置问题已纠正：other成员已由上游fixture创建，重复插入造成非唯一成员；直接fence=true但enabled仍true违反既有绑定约束。改用独立query-other成员及合法binding revision推进，未放宽产品检查。

完整head迁移已包含035；主库仍030未变。AR2扫描1847模块/163分类/93迁移，全部错误数组为空；git diff --check通过。项目记忆投影CURRENT，memory-validate GREEN，authority仍AOS-000573，不声称本波获得父清单完成授权。

下一波UQ4-B：独立受限API连接身份、请求提交与查询HTTP、错误脱敏和no-store；再Web等待/资源撤下，UQ5签名包，UQ6真实安装读取和UQ7经营首链八场景。
