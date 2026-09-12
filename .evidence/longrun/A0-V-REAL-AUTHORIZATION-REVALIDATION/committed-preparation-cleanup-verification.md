# 已成功准备的清理收尾实证

基线9b7ca72f；新增committed_cleanup复用既有runtime权限和RLS，不新增角色、授权或迁移。自动恢复批次每次最多100项，当前版本竞争只跳过CAS冲突，其余身份/数据错误继续fail-closed。PreparationWorker复用相同收尾。

验证：新增收尾案例先红14项；修正测试样本使其遵守事件编号、绑定约束及不可变历史后，累计84 passed/1 skipped（专用OCI opt-in未开，本波PG覆盖真实运行，未声称该OCI测试通过）。包含重放、回滚、未知/未释放、缺失/坏hash证明、错generation、仍启用、租户、CAS、特权身份拒绝，以及原资源恢复/worker/Host回归。

正常Host v12(pid61252)载入后自动将主库08c58e06从needs_attention@61收尾为failed@62，failureCode PREPARED_RUNTIME_RELEASED；phase保留succeeded，原preparation_committed@12 hash204e04f0...不变，仅追加committed_preparation_released@62。前后证据分别为ecommerce-committed-cleanup-before/after.json。

原禁用命令同键重试正式accepted，Operation6286f967-a0a8-45ba-bd7b-98d4feb66bf2实际succeeded@6。binding同generation、revision7、desired disabled、observed unknown、enabled false、fenced true、epoch5；disabled_committed含exacttarget及hash。再次同键执行replayed=true、同operationId，未创建新命令。参见ecommerce-sleep-disable-request/completed/replay.json。

阶段验证器ar2-7：1789模块，158分类，93迁移，五类错误均空。主库未加DDL/权限，无Provider或业务调用；没有复活旧generation。当前尚未卸载重装，已enable未dispatch的卸载合同仍缺。下一波先补此合同的严格方案及隔离验证，不能套never_enabled，也不混入待批的路由登记权限。
