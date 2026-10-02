# E17-a2b｜Growth 1.13 隔离发行失效负例与正式预检下一步

## 上位方案/基线

231-2 的运行制品准入要求精确 lock、不可变签名字节、当前信任根与撤销状态、OCI image digest；231-3 的 ready binding 必须与 active 安装 revision、generation 和 lock 同代，且 enabled/fence/epoch/权限/预算/策略仍逐次校验。E17-a2a 已在可销毁 PG/独立 OCI 通过 Growth1.13 原生产者正链，但当前真库仍是四旧包 approved/binding0，正式 OIDC/信任根/身份/八配置/Owner 缺失。此波只能证实隔离负例，不给当前实例执行许可。

## 文件级实施与 RED

1. 修改 `services/aos-api/tests/extension_runtime/test_growth_113_current_release_evidence_pg.py`：在原 Registry/安装正例后，用**测试私有签名树副本**改 Growth image index 字节，要求 ManifestLoader/读者失败封闭；用原 RegistryService 撤销 Growth1.13，要求当前 release 读者拒绝。测试不得触碰仓外原签名树。
2. 修改 `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：在原 `admit_runtime_artifact` 的 Growth 成员加入 image-index 字节/digest 篡改拒绝；确认 binding 的 generation、installation revision 和 package lock 引用同代。若数据库保护使错 lock 的直接篡改不可达，记录不可达/具体保护，不通过关闭保护造负例。
3. 对正式 API/Host 预检只做文件级复审：E17-a1 读者可复用，但现在是证据视图且没有 OCI/Owner 准入；受限 API 与 Host 仍调用旧四包/binding0 preview 谓词。下一波独立新增正式视图及启动选择，必须先具备可核验的正式 trust/OCI/OIDC/三身份来源；本地测试签名只供隔离测试。

先运行新增负例观察 RED/现有拒绝结果，只补有证据的最小缺陷；专项用独立 pytest 会话避免两条测试在同一临时库重复发布同四个 Registry 坐标。旧 1.12 完整链与 E17-a1/启动门相邻回归、语法/diff、浏览器禁入回读、方案/代码一致性和独立容器/测试库清理一并验收。当前真库只读、Host/worker/Provider 关闭；不读取商城源、不重放旧 12 Run、不手工 run_definition、不碰 230 L0、不 push。
