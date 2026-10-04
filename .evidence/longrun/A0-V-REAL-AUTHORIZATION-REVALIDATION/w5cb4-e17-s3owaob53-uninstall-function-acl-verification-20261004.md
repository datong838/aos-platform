# b53｜正式卸载函数 ACL 只读证据

## 当前库只读复核

- `scripts/a0v_current_preview_http.py` 正式签名预检 exit0 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN` 后，使用它返回的确切连接参数、`SET TRANSACTION READ ONLY` 查询；首次临时查询脚本把 preflight 的第二个返回值误作连接参数，exit1 `invalid connection option database`，没有任何数据库写入；修正返回值顺序后 exit0。
- 结果：`aos_current_preview_20260927@a0v_135`；`has_function_privilege('aos_runtime','extension_runtime_uninstall_commit_ar2_018(uuid,bigint,text)','EXECUTE')=false`；同函数 `aos_app=true`；`pg_has_role('aos_runtime','aos_app','member')=false`。命令只读，无 DDL/GRANT/安装操作。
- 原 `ar2_018_runtime_uninstall_authority.py`：PUBLIC/aos_runtime/aos_extension_maintainer 撤 EXECUTE，只给 aos_app；函数内要求非特权 `session_user` 为 aos_app 成员，安装 active、唯一 Binding、disable detach Receipts、资源释放与无在途尝试才追加 uninstall Receipt。标准 `db.connect(scope)` 在同租户事务中切 `aos_runtime`，因此当前 ACL 使合法 active 路径在进入函数体前就被拒绝。

## 一致性/风险

- b52 的缺 Binding 修复独立成立并失败关闭；本波确认剩余是“合法路径不能执行”的 ACL/身份缺口，未据此给真实库提权。当前代码和库头均135；单独新增136会破坏每日最新栈签名预检，且与 Capability issuer/受限锁迁移候选冲突。
- 下一波在完整 disposable signed 克隆设计最小正式执行角色和函数授权，做无 EXECUTE→拒绝、精确授权→合法受控正向，以及错租户/无排空/未知副作用/重放的反证。正式当前卷迁移须另波的新独立备份、全恢复、零执行窗口。Host/worker/Provider关闭，首链仍 pending。
