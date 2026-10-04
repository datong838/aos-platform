# b52｜active 运行安装缺 Binding 时旧卸载失败关闭

## 方案/代码复审

- 上位 231-3 要求 runtime 卸载先停用、排空、确认资源释放，再原子追加安装 `uninstalled` 与 Receipt；旧路由不能把缺少 Binding 当作纯内容。`ar2_018` 函数在 active 安装 Binding0 时返回 `(false,NULL,NULL)`，原 `RuntimeUninstallGuard.before_uninstall` 返回 `None` 后，`InstallationService` 继续追加旧 uninstalled。
- 完整 signed Growth1.13 disposable PG/OCI 原安装与准备/验证达到 active。只在此可销毁库删除其 Binding，作为损坏状态负例；创建随机无特权 app 登录并仅在测试期间向 runtime 角色授函数 EXECUTE，用以越过另一独立 ACL 缺口。原路径 RED exit1 `DID NOT RAISE RuntimeOperationRequiredError`，确认确实追加旧卸载。测试结束撤销临时 EXECUTE 并 DROP 登录；不把故障注入当合法换代生产者。
- 生产最小改动：`InstallationService._append_uninstall` 向既有 guard 传当前 `StoredCompositionLock`；guard 对 active 非纯内容查询精确 Binding，无 Binding 则409 `RUNTIME_OPERATION_REQUIRED`，不触发底层空结果，也不追加安装命令 Receipt；纯内容锁沿用现有 `legacy_content_predicate`，保持旧卸载。`approved` 无资源分支沿用原合同；本波不修改唯一135迁移/当前真实库。
- 隔离签名负门 green 后回读 active/current/ETag 不变、旧 uninstall 命令 Receipt0；纯内容 active 的 guarded rollback 和 uninstall 均正向 `etag6`。原 signed 完整正向仍通过。

## 命令与退出码

| 命令 | 结果 |
| --- | --- |
| `AOS_B52_MISSING_RUNTIME_BINDING=1` 的完整 signed Growth1.13 PG/OCI pytest（其余 env 与 b51 verification 同） | 原路径先被独立函数 ACL 拒绝（exit1 `InsufficientPrivilege`）；隔离临时测试授权后得到目标 RED exit1 `DID NOT RAISE`；生产 guard 修补后 exit0，1 passed/7 warnings。 |
| 同 signed pytest 去掉 b52 模式 | exit0，1 passed/7 warnings。 |
| PG 纯内容/InstallationService/approved guard/control wiring 四文件 | 全跑 exit1：原 `test_runtime_control_plane_permission_locks_the_current_installation` 假连接无 `info` 属性，17 passed/1 failed；排除该旧测试复跑 exit0，17 passed/1 deselected/7 warnings。该失败不在本波改动文件，仍需独立修复。 |
| `test_current_installation_release_evidence.py`、`test_aip_binding_readiness_service.py`、`test_release_revalidation.py` | exit0，32 passed/2 strict xfailed/7 warnings。 |
| 四改动文件 `compileall -q` 与 `git diff --check` | exit0。 |

## 剩余风险与下波

- 正式 DB 函数 `extension_runtime_uninstall_commit_ar2_018` 当前只授权 `aos_app`，而标准 `connect(scope)` 切到 `aos_runtime`；隔离测试先被 ACL 拒绝，说明正常 active 运行卸载还须独立角色/迁移设计。不可在当前135卷直接 GRANT；唯一136及正式身份/全恢复/零执行窗口另波。
- 本波仅封住“Binding 缺失→旧卸载”绕路，不证明合法运行卸载/重装、正式 trusted available 或首链。当前库只读、Host/worker/Provider关，正式 OIDC/Issuer/Reader/Owner、active Growth1.13、八配置/六 Binding仍缺。生产 API 需加载提交并做只读复核。
