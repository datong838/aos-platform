# E17-a2b｜Growth 1.13 原链失效负例 verification

## 范围与结论

依 `w5cb4-e17-a2b-failclosed-plan-20261002.md`，仅在 pytest 自动销毁 PG 和独立 OCI 使用仓外 local test-only Growth1.13 签名树；原签名树及当前真库没有写入。新增四个失效检查：原安装 revision 的 lock hash 直接改写由数据库不可变触发器 `23514` 拒绝；测试私有签名树副本的 Growth image index 多一字节时，E17 发行读者返回 `RELEASE_BYTES_DRIFT`；原 RegistryService 撤销 Growth1.13 后发行读者失败关闭；原 `admit_runtime_artifact` 拒绝被改动的 image-index 字节。正链仍能由原 producer 到 active、同代 ready binding，但 binding disabled/fenced 且无 dispatch，输出仍 `EVIDENCE_ONLY_NO_START`。

## RED、验证、复审

- 新负例首测误把读者的精确 `RELEASE_BYTES_DRIFT` 断言为泛化 `RELEASE_EVIDENCE_INVALID`，退出1；按真实合同改断言后 PG-only `1 passed, 7 warnings`，退出0。并发启动两套独立 PG pytest 时，共享 `aos_runtime` role 迁移出现 `tuple concurrently updated`，测试 setup 退出1；改为串行执行后两条链分别通过。后续相同 role 迁移测试不得并行跑。
- `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_GROWTH113_SIGNED_RECEIPT=... PYTHONPATH=services/aos-api .../pytest -q ...test_growth_113_current_release_evidence_pg.py` → `1 passed, 7 warnings`，退出0。
- 同命令加 `AOS_EXTENSION_OCI_TEST=1`，运行 `...test_growth_signed_installation_full_schema_pg.py` → `1 passed, 7 warnings`，退出0；其 `admit_runtime_artifact` 对篡改 index 的失败在真实正例之前发生。旧 Growth1.12 r3 Receipt 同测试 → `1 passed, 7 warnings`，退出0。
- E17-a1 读者/旧预览与 Host 启动门/ReleasePolicy/UI 五文件相邻回归 → `36 passed, 7 warnings`，退出0。`py_compile`、`git diff --check` 退出0。独立 OCI owner 容器集合空；测试仍未启动当前实例 Host/worker/Provider。
- 当前只读 preview preflight 回读：`a0v_135`，`aos_current_preview_20260927`，approved，4 个旧发布，binding0，退出0；它不代表 Growth1.13 正式发布。浏览器 `/aip/skill-publish` 仍 37 仅评测/发布0/三 blocker/按钮禁用，电商导航无可见入口；截图 `w5cb4-e17-a2b-browser-20261002.png`。

## 方案/代码一致性与下一门

只修改两份隔离 PG 测试，生产读者/预览/API/Host 门禁没有放宽。可达的错 lock 写入被数据库原不可变机制拒绝，没有关闭触发器制造伪负例。旧 generation/epoch 的正式 Owner 负例仍须随下一波版本感知预检/Owner 联合测试建立；本波不声称已证明当前正式信任根、OCI、OIDC、三身份、八配置、assignment、当前 binding 或首条自然业务链。下一波把 E17-a1 证据读者接为**独立正式模式**，在隔离原生产者实例先 RED，当前实例缺正式外部权威继续禁入；不以本地 test-only 签名升格。
