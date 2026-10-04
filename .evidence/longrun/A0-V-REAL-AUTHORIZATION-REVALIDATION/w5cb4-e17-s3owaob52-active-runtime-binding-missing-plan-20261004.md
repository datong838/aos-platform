# b52 文件级方案｜active 运行安装缺 Binding 时旧卸载禁入

## 上位与现状

- 231-3 §1/§3：runtime 卸载须走 RuntimeOperation、停用排空、资源释放、原安装 uninstalled 与 Receipt 原子提交；旧 uninstall 不得绕过，纯内容旧合同保留。BIND-1 最终可信来源仍未完成，当前真实库只读。
- `RuntimeUninstallGuard.before_uninstall` 读取 active 安装后调用 `extension_runtime_uninstall_commit_ar2_018`。该函数在 `v_binding_count=0` 返回 `(false,NULL,NULL)`；Python 将其作为 `None`，`InstallationService._append_uninstall` 随后无条件追加 `uninstalled`。对运行包的 active 安装，零 Binding 不是可确认的纯内容，只能失败关闭。
- 上述为源码推论，需在 disposable signed Growth1.13 PG/OCI 复现后才算缺陷确认。不得改当前135迁移或真实卷；不直接使用 owner 角色做正向卸载证明。

## 文件级最小施工

1. 扩展 `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` 的独立 b52 模式：原签名包经正式安装路径达到 active；在可销毁克隆做故障注入使 Binding 缺失，调用原 `InstallationService.uninstall`，RED 判据是它成功把 active 改 uninstalled/产生命令 Receipt。该注入只是负向损坏状态，不当成合法生产者。
2. 若 RED 成立，修改 `services/aos-api/aos_api/extension_runtime/runtime_uninstall.py` 与 `services/aos-api/aos_api/asset_registry/installation_service.py` 最小传递当前锁，并在缺 Binding 空结果时对非纯内容锁返回409 `RUNTIME_OPERATION_REQUIRED`；纯内容原卸载继续。不得将 `false,NULL,NULL` 当作成功资源释放。
3. 跑签名 b52/原模式、纯内容卸载、运行卸载相邻与 b48–b50 安全集；检查方案/代码一致性、状态/Receipt 无半写。适用时重启生产 API 并浏览器/只读验收。

## 边界

此波只关缺 Binding 的失败关闭，不能证明合法卸载/重装、trusted available 或首链。Host/worker/Provider继续关闭，真实库只读；唯一136迁移和当前卷切换独立后波。
