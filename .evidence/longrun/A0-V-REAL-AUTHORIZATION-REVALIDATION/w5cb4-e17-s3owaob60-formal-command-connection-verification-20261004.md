# b60｜安装卸载专用低权连接预检验证

## 方案、RED、实现

- 上位 231-3/231-4 与 b58/b59 方案复习及文件级计划在同名 plan。`test_uninstall_command_connection.py` 首次收集 exit2 `ModuleNotFoundError`；新增 `control_wiring` 注入负门首次 exit1，确认此前只有普通 Store。
- 新 `asset_registry/uninstall_command_connection.py` 只接受绝对路径、nofollow、0600/当前 UID、精确 schema 与唯一 JSON 字段的受保护文件；拒绝同 Web 用户/DSN、目标库/端口/host 不同、hostaddr/service/session options 绕过；连接后先只读核对 session=current=指定角色、LOGIN/NOINHERIT、非超管/BYPASSRLS/建角色/建库/replication、仅有不可继承不可 SET 的 app 成员、非 runtime 成员、无受保护 Binding UPDATE。核验后才把同一连接交给安装命令事务，失败不回退普通身份。生产 Binding 权限核对固定 `public`；isolated 夹具通过内部参数指定独立 schema。
- `control_wiring.py` 的 canonical Installation 与 RuntimeControlPlane 仅在设置专用身份文件引用时注入独立 Store；文件缺失时旧普通命令路径保持原样，运行卸载仍由既有 `ar2_018` 高权拒绝失败关闭。文件有误时命令打开连接即拒绝，不借用普通连接。没有迁移、GRANT、当前库写入或 Host 启动。

## 验证

- 保护文件/DSN 负门 9 项（含缺文件、宽权限、符号链接、重复字段、同 Web DSN、hostaddr、会话 options、错目标、角色漂移）专项 exit0；生产组装 opt-in/默认路径测试 exit0。
- isolated PG/OCI signed 两代次全链 exit0；命令身份替换为超管、INHERIT、runtime 成员、额外 `pg_read_all_data` 成员、Binding UPDATE 均被拒绝，回滚角色后正常签名卸载/重装、两个 Receipt 与 OCI 资源回收仍通过。
- 专项与相邻 `pytest` exit0 `33 passed/1 deselected/7 warnings`。排除的旧 `test_runtime_control_plane_permission_locks_the_current_installation` 仍因 fake connection 无 `.info` 失败；不将其记为通过。`git diff --check` 待最终复核。

## 局限与下一步

- isolated 夹具的受保护文件只是本地测试身份；生产正式凭证尚无，当前 `aos_current_preview_20260927@a0v_135` 没有正式低权角色/ACL，不能从这波代码推断当前安装可卸载或首链完成。正式来源、当前 Growth1.13、八配置/六 Binding仍待证。
- 当前库迁移/切换与唯一136 Capability/安装锁/evaluator 合并审查，必须新备份、全恢复演练、零执行窗口。下一波 b61 审正式凭证来源、角色/ACL迁移合同与独立预检；Host/worker/Provider继续关闭。
