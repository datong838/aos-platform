# E17-a2｜Growth 1.13 原生产者隔离正反链文件级方案

## 上位约束与当前基线

按 231-2/231-3、E17 正式启动/Owner 方案和 D-waves E17-a2 条目执行。当前 `m1@a1c82f23` 的发行证据读者只证明旧四包的当前只读路径，固定输出 `EVIDENCE_ONLY_NO_START`。权威库 `a0v_135`、`org-org/dev-project` 的 Growth 1.13 当前发布、八配置、Host assignment/identity、binding 均为 0；受限 API 和 Host 分别以外部 OIDC、凭据缺失失败封闭。此波不得写权威库、提升本地测试签名、启 Host/worker/Provider 或把旧 preview 预检改成正式预检。

## 文件与最小步骤

1. 在 `services/aos-api/tests/extension_runtime/test_growth_113_current_release_evidence_pg.py` 增加仅显式环境启用的可销毁 PG 测试。读取仓外现有本地 Growth 1.13 签名 Receipt，核精确四包、树哈希、trust-root revision、ManifestLoader 原字节及 ReleasePolicy；不读取签名私钥。
2. 仅通过原 RegistryService 建立四包 published、原 `create_approved_first_installation` 建 approved@3 exact lock；调用 E17-a1 读者证明新 Growth 1.13 的 bundle/version/hash 与 lock 一致。负例覆盖错租户、撤销/空 trust、签名字节改动；测试所有写入限于 pytest 自动创建并删除的 `aos_test_*_ti4_test`。
3. 另一步接原 RuntimeLifecycleService/PreparationWorker 的 apply→verify 和同代 ready binding，复用已归档 1.12 全 schema 测试的受控 OCI 路径；对旧代、错 lock、撤销和 digest 做 RED。若本地 OCI 或授权不齐，记录精确失败，不伪造 binding。

## 验证和收口

先 RED 再实现最小测试/必要代码；专项与相邻安装/读者测试、语法/diff，必要时浏览器确认现行禁入。正例只证明隔离代码链，不是当前正式发布、OIDC/三身份/八配置、Host Owner 或自然首链。方案/代码复审、verification、D-waves 和 01/06/Prime 更新后精确提交。下一步继续正式信任源与 API/Host 启动预检，当前实例继续失败封闭。
