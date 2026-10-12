# 当前恢复入口冻结一致性

Rules：AGENTS.md、231八步、已批准栖月汇恢复方案，parent原Task/Lease。候选一是最新冻结启动源准备，候选二是正式OIDC/独立publisher接入（配置来源待定位）。选择一，不重启或迁移真库。

上轮恢复入口修复后检查冻结消费者：当前核对API和旧preview入口，却不核对实际被新进程导入的a0v_qyh_restored_http.py。因此仅恢复入口提交发生变化时，旧冻结消费者可能被接受，随后执行旧入口。这会丢失刚修复的161检查。

先用已有隔离Git夹具新增仅恢复入口提交变化的RED；最小修复将该入口纳入原git blob精确对比，不改变源报告/权限/hash/分支门。具体代码文件仍为scripts/a0v_qyh_restored_http.py与services/aos-api/tests/extension_runtime/test_qyh_restored_http.py。通过专项/相邻后复用原freeze_current_api.py生成最新候选并真实消费验证；私有源码不提交，不新启API/Host/worker。
