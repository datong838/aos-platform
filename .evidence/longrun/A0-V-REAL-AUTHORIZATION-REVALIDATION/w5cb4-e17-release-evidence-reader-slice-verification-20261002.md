# E17-a1｜当前安装发行证据只读读者验证

## 目标与界限

按 231-2/231-3 和 `w5cb4-e17-release-evidence-reader-slice-plan-20261002.md`，新读者只组合原 Installation/lock、RuntimeReleaseRevalidator、ManifestLoader 三种原权威，输出 `EVIDENCE_ONLY_NO_START`。未连接 API/Host 启动器，未改 pinned preview、业务派发、数据库结构或当前真实库数据。

## RED→GREEN

| 步骤 | 实测 |
| --- | --- |
| RED | 新 `test_current_installation_release_evidence.py` 引用尚不存在的读者；`pytest -q` 收集失败 `ModuleNotFoundError`，退出2。 |
| 最小实现 | 新增 `services/aos-api/aos_api/extension_runtime/current_installation_release_evidence.py`。函数自开 `REPEATABLE READ READ ONLY`，精确查租户安装/current revision/ETag；原 `load_stored_lock` 校验 lock；原 `RuntimeReleaseRevalidator` 以当前 Registry/ReleasePolicy 验所有已选发布；`ManifestLoader` 逐包核签名原字节、manifest/content hash。返回冻结 dataclass，`authorization` 字段不可由构造者覆盖且固定为 `EVIDENCE_ONLY_NO_START`。 |
| 当前真实库只读专项 | 显式 `AOS_E17_READONLY_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json`，四项：当前 org-org 安装 approved@3/active NULL 的四个旧签名包证据可读；dev-org 同安装不可读；空 trust root 与缺签名 source 均拒绝。`4 passed, 7 warnings`，退出0。这里的预览签名仅验读者，绝不是 Growth1.13 正式信任根。 |
| 相邻回归 | 同命令含当前预览 HTTP、Host 身份预检、原 release revalidation、UI source reader 五文件，共 `36 passed, 7 warnings`，退出0；最终最小变动再跑本专项 `4 passed`，退出0。`py_compile`、`git diff --check` 退出0。 |
| 页面 | 内置浏览器 `/aip/skill-publish` 只读回看：37项仅评测、0发布、三阻断、发布按钮 disabled、电商导航无可见入口。截图 `w5cb4-e17-release-evidence-reader-browser-20261002.png`。 |

## 复审与剩余风险

- 与方案一致：只读发行证据是正式启动链的必要前置，但它不证明 OCI 实际镜像、外部 OIDC、独立 API/Directory/Runtime/Web/Host 身份、八配置、精确 Host assignment/Owner、active binding 或自然首链。函数没有可执行许可返回，也没有连接当前启动入口。
- 当前正例是四个旧 pinned 签名包，**尚未证明 Growth1.13 正式发布/同代 binding 的新路径**；下一波须在可销毁 PG 用原 Registry/安装/lifecycle producer 做 Growth1.13 正反链，再将正式根/OCI/身份/Owner逐门接入。当前库只读、Host/worker/Provider关闭，预览栈继续禁入。
- `RuntimeReleaseRevalidator` 的事务锁和两次 Registry snapshot 都在同一个可重复读事务中；后续启动必须在消费时重新读取，而不能把这份 evidence 跨事务当许可。
