# SC4-5f4b 原子组认领Owner

2026-09-14，基线88841987；Lease A0-V-SC4-SNAPSHOT-GROUP-CLAIM-OWNER。

固定复用原SourceClaimOwner及GroupOwner；canonical body绑定完整当前draft/control/run/actor/tenant/group，复用Ingress _digest。新组所有原claim必须created=true，否则拒绝；已有组严格核对body/hash/成员并read_current，不reserve、不源读。保存点只在调用者已有事务内打开，成功不自行提交。

缺模块红测后8项隔离PG通过。新增“预存最后一个原claim、组内先新建前项、调用者捕获错误后提交”反例，实测1 failed/8 passed；保存点修复后组合原claim/schema共41 passed/7既有警告/10.07s。验证回滚后预算可用、停止运行拒绝重放、actor/run漂移和当前拒绝。签名资产fixture，原控制/claim/组数据库记录真实；没有真实源读取或主安装验证。

AR2 1912/187/93五数组空；memory validate与diff-check通过。下一组输入持久化与受控一次读取，created不是可外带的源许可，提交确认与再次当前核验仍必须由后继执行器完成。

SC4-5f4b：组认领Owner完成，41项隔离PG回归通过；两成员原认领+组日志原子创建/精确重放/旧认领拒绝。审查新增捕获异常后提交反例，先红后以保存点修复半组残留；原外层事务所有权保留。下一同事务一次读与组输入持久化/未知结果核对，再真实关系及补齐；主首链未完成。
