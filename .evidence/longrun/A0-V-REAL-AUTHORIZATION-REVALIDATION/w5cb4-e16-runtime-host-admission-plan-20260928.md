# W5CB4 E16：运行命令受理与 Host 可执行性分离（2026-09-28）

## 上位、现状与目标

复习 231、231-3、231-9、栖月汇产品方案及 E15 verification。业务目标是用户从产品入口安装、配置、自然触发首链，不靠开发者手工接 Run。`runtime-apply`/`runtime-verify` 是独立运行包生命周期；受理回执不是资源已准备/已验证。当前 m1 `74685227`、当前卷 `aos-a0v-recovery-pg-data`、schema `a0v_109`，唯一安装 approved/revision3/ETag3、active 空，runtime operation/binding/Host assignment0。8080/8434 可读、18181 关闭。当前 `.env` 的 `AOS_BUNDLE_ROOT` 指向已不存在的旧目录，Host 启用与独立目录/运行身份所需开关/凭据未配置；不可把 `allowedActions` 解读为 Host 已在消费。

## 文件级执行清单

1. 只读盘点当前 bundle 制品、签名/Registry 精确引用、当前卷 Runtime Host assignment、进程 Host 状态、独立 web/runtime/directory 数据库身份与 OCI context；不输出秘密正文、不读商城源。明确哪些是已有正式权威、哪些只是开发预览。若身份/Owner 缺失，禁止提交 `runtime-apply`，不使用旧 `aos_meta_head` 或特权账号捷径，也不创建未审批假身份。
2. 先 RED 测试：当前 Host `INACTIVE` 或 task 已结束、无当前租户 assignment 时，页面不得给出“可执行运行资源”的假象；任何保护都不能把已有未知回执误判为可重新发送。优先修改 `services/aos-api/aos_api/routers/bundle_runtime_installations.py`、`extension_runtime/runtime_view.py` 或更窄的服务组合端口，在受理前由可信进程/目录权威给出**只读、当前**准入结论；若现有契约没有可同时保证授权、原幂等回读和 Host/assignment 当前性的安全接缝，先完成只读可执行性投影及前端禁入，不仓促改变 POST 语义。
3. 前端仅在权威 Host/assignment 明确就绪且 runtime view 与当前安装 ID/revision/ETag 匹配时开放运行准备/验证按钮；`null`/缺失/过期/离线/未选安装一律禁入，服务端仍为最终围栏。文件范围预计 `apps/web/src/api/assetControl/{types,runtimeInstallations}.ts`、`apps/web/src/pages/s2/{AssetBundlesPage.tsx,assetBundles/RuntimeInstallationPanel.tsx}` 及对应测试。纯内容旧动作、配置、审批与既有 Receipt 不受影响。
4. 专项测试覆盖 Host active/inactive/failure、assignment 有/无/漂移、跨租户/错安装、读失败、已有未知回执/幂等重放；累计相邻 Registry/runtime 与前端套件、TypeScript/构建。浏览器只读验收当前运行面板如实禁入；不点击任何会生成 operation 的按钮。
5. 方案/代码一致性与安全复审、verification 落盘、m1 精确提交、AOS/Prime 上下文更新；立即进入 E17 的当前身份/Host/OCI 正式启动及首链准备。当天代码变更后，以最新 m1 与同一权威命名卷完整重启 DB/API/Web，读回版本、页面、健康、Host/operation/binding/Receipt，再继续 Loop。绝不删除数据卷、不 push、不重发旧 12 Run、230 L0 仍挂起。

09:00 现场收窄：重启证据 `bf4dee67` 确认 Host/assignment0，但 API 运行面板仍露出“准备运行资源”。实现接缝定为 `extension_runtime/runtime_host.py` 的当前同 scope preparation assignment 只读判定、`routers/bundle_runtime_installations.py` 的当前进程 Host task + assignment 投影及每次 POST 注入、`extension_runtime/lifecycle_service.py` 的**新命令 handler 内**准入复核（在幂等 Receipt 读回之后、operation accept 之前，保留同 key 对账）。前端 `RuntimeInstallation` 严格 DTO 加 `preparationExecutable`，仅为当前可执行性提示，受服务端最终检查约束；对 `runtime-apply/verify`，页面按钮与 controller 都在该字段非 true 时禁入。已有未知结果的按钮不得重新 POST；只保留只读对账提示。服务端 Host 状态在读与提交之间可变化，必须再由 handler 读当前，不能把 GET 当永久许可。

九步：1 上位复习；2 文件级方案；3 RED/最小实现；4 专项；5 累计；6 浏览器；7 一致性复审；8 verification；9 提交/记忆/下一波。停止门：未知结果、身份/assignment/签名不明、测试失败或提交边界不明时冻结动作，仍可推进只读诊断和独立编码；不得将 HTTP200 或按钮可点当业务完成。
