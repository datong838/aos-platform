# W5CB4 E15：当前安装纯内容路径权威禁入验收（2026-09-28）

## 结果

本波完成 E13/E14 后继的**真实页面禁入**：当前运行包安装经服务端当前租户、current revision/ETag 和 exact Registry 行判定，通用 Apply 被禁用；浏览器明确显示“服务端判定不可用（运行包或 Registry 不一致）”。没有点击任何安装或运行写动作；安装仍 approved/revision3/ETag3、active 空，runtime operation/binding/Host assignment 均 0。此处只区分旧纯内容路径可否作为候选，**不证明**包签名/发布状态、运行 Host 可用或首链成功。

## 九步证据

1. 复习产品 12、231/231-9 BG-00、231-3 和 E13/E14 verification；先行计划 `57c083a1`。
2. 文件级方案复用 `asset_registry/legacy_runtime_boundary.py` 的 fail-closed predicate；修改 `extension_runtime/runtime_view.py`、`asset_registry/control_wiring.py`，在 runtime view 已授权后的同一租户只读事务，以安装 ID/current revision/ETag 联合 current lock 读 `legacyContentEligible`。查不到唯一精确行、版本/hash/manifest 不自洽均为 null/false，不以最新版本猜测。同步严格 API DTO、TypeScript parser/type、页面动作策略/控制器与测试。
3. 最小实现让前端只在安装详情与 runtime view 的 ID/revision/ETag 均一致、无 stale/refresh 且服务端字段 `true` 时开放旧 Apply/Verify；`false`/`null`/读失败时按钮和 controller 零 POST 禁入。服务端 E14 的 `RUNTIME_OPERATION_REQUIRED` 仍是最终围栏。首轮浏览器发现新服务端字段被前端严格 parser 拒绝，运行面板显示读取失败；补齐 parser 字段与反证测试后修复，未在失败期间执行写动作。
4. 专项：`test_runtime_installations_api.py` 23/23，frontend action/controller/面板 39/39，runtime parser 7/7；纯内容 true、运行/未知 false/null、错 revision/ETag 与 Registry 漂移逻辑均受测。
5. 后端相邻集合 41 passed、14 skipped（缺隔离 PG 前置，不计通过）；前端累计 307 文件 2693/2693、TypeScript 无报错、Vite build 通过。另追加 `test_control_wiring.py` 相邻诊断：原 `.env` 的旧 `AOS_BUNDLE_ROOT` 已不存在，导致 4 项环境失败；以现有构建目录作**仅测试进程覆盖**复跑后为 8 passed、2 failed。余下两项分别是旧惰性导入断言（本波 `control_wiring.py` 改动只在函数内导入，不影响模块加载）和 SQLite `Connection` 缺少 psycopg `.info` 的旧测试夹具失配；两项均与本波读投影无因果关系，列为测试债，不伪称全绿。既有大 chunk 告警与本波逻辑无直接关系。
6. **最新代码再次全面重启原 DB/API/Web**：PG 容器仍挂载命名卷 `aos-a0v-recovery-pg-data`，库 `aos_current_preview_20260927` schema `a0v_109`；8080 health `ok`/ready `ready`、8434 HTTP200，18181 无监听，Host/worker 0，runtime operation/binding/assignment 0。浏览器 `/apollo/assets` 重读唯一安装 approved/revision3/active 无，运行状态 `not_prepared`/无绑定，`执行 Apply` disabled 且服务端判定不可走旧路径。没有读微商城源。
7. 方案/代码复审：只新增读投影与前端禁入，没有变更安装/Runtime Store、幂等 Receipt、预算/权限和业务副作用。分类 true 仅是**通用路径候选**，不能替代最终 Registry/签名/授权复验；false 同时可能是运行包或 Registry 漂移，页面未误称确定原因。不同事务读回的安装详情与 runtime view 用精确 ID/revision/ETag 对齐，最终服务端仍 CAS；全链竞态仍 fail closed。
8. 本 verification 落盘；E15 的新增行为按狭义验收为绿，但相邻 `control_wiring` 两项既存测试债保留红灯，不能称整个相邻套件绿；首链仍未启动。
9. 精确提交代码/证据，更新 AOS/Prime 上下文后进入 E16。E16 优先修当前运行面板在 Host/Owner=0 时仍显示可提交 `runtime-apply` 的准入缺口，并规划当前卷独立身份/Host/OCI 正式启动；不得向无 Owner 队列投未决命令，不用旧 `aos_meta_head` 或特权账号捷径。每日继续以最新 m1 与当前命名卷全面重启、自检、立即 Loop；不 push、旧 12 Run/230 L0 保持冻结。
