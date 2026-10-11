# 固定fmgr调用事件覆盖校准

Rules231，唯一m1，原Goal active，不更新Codex。候选一正式栖月汇恢复需既有publisher/OIDC；候选二A1862已登记受限原生事件探针覆盖校准，选择二。先读当前本地fmgr.c/fmgr.h：builtin fastpath在needs_fmgr_hook检查之前返回，fmgr_security_definer分支有START/END/ABORT；不假定fmgrhook能覆盖所有内置或直接C调用。

文件仅本Task目录plan.md/probe.c/Dockerfile/check.py及构建/验证/复审资料。固定aos_app superuser且精确r5隔离DB/容器/image/cluster。helper bool仅触发固定除零失败；无任意OID/SQL/payload参数，无PG自动初始化hook。单次helper内拒绝已有hooks，安装temporary needs/fmgr hook，直接调用当前pg_temp固定proconfig SQL wrapper正例；固定builtin length fmgr_info路径与DirectFunctionCall1(textlen)为负覆盖，三条返回均8。不收业务payload，仅函数OID/event/计数及固定结果。正例wrapper源码由driver创建并精确核对，原Source不重放。

固定SQL wrapper VOLATILE+SETsearch_path防内联，abort wrapper固定SELECT1/0用于实际START/ABORT。PG_TRY/PG_CATCH正常/失败均恢复两个hook pointer与active状态；scope错误/已有hook拒绝不夺已有hook。离线SDK/hash严格编译、newlibrary唯一hash路径，不覆盖旧so。旧so缺新symbolRED，正常→强制ERROR→正常重复精确、runtime身份真实拒绝→再正常；事务内helper/wrappers/GRANT/marker全部ROLLBACK，独立callerXID aborted/helper消失/九表零/原194函数hash保持。

正常记录不证明未记录的builtin/direct路径未执行；真实负覆盖必须执行且返回正确结果、事件计数不增。这是覆盖反例和有限入口可用性，不是完整native闭包、正式Root或自然COMMIT验收。保持正式库和现有22处改动、旧审批预算/Host/worker/Provider不变。其覆盖缺口约束后续Source方案，不以强行绕hook或替代调用改变原业务语义。

编译r1在FunctionCall0不存在处RED，未产出或加载so。按原fmgr.h声明最小改为FunctionCall0Coll且InvalidOid，保留r1源码/hash/build.log；r2仍严格编译，不降低告警。
