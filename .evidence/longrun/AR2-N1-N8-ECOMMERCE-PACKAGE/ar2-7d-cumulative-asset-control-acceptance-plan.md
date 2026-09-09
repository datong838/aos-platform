# AR2-7D 累计回归与资产控制可点击验收方案

日期：2026-09-10
基线：`m1@98379e3d`
状态：`REVIEWED_IMPLEMENTATION_PLAN_AR2_7D_CUMULATIVE_NEXT`

## 1. Rules 与边界

- 以 closure manifest、231-6 AR2-7D 可点击前置验收卡、D1～D6 已提交证据和当前 m1 为权威；m1 单人串行，先方案后执行，失败修复后重跑受影响集，证据与提交完成再进入 7E。
- 本段只封存 AR2-7D：九条 signed path/API 的 authority 反证、9/9 cutover、签名物理生命周期、累计回归，以及资产控制页的安装/运行状态、操作可见性、刷新和 slot 可见性。八工作台逐页视觉、栖月汇真实只读经营数据和自然自动链属于 7E/A0-V，不在本段伪造。
- 浏览器主路径固定为当前 m1 Web `127.0.0.1:8434`。测试 API 使用隔离、确定性 fixture 或浏览器路由拦截，只呈现 D6D2 已由真实 PostgreSQL/OCI 证明过的状态形状；浏览器证据不能替代 D6D2 authority 证据。
- 不执行真实租户装卸、真实业务 mutation、真实 Provider、费用、共享/生产迁移、外部发布或 push；`org-org/dev-project` 只作正向 scope，`dev-org/dev-project` 只作负向 canary。230 L0 继续挂起。

## 2. 累计回归门

1. 固定当前 HEAD、工作区范围、Docker context、两个隔离 PostgreSQL 和 OCI 残留基线；恢复 8434 Web 仅用于本地验收。
2. 后端依次运行 `tests/asset_registry`、`tests/extension_runtime`，并补齐 AR2 N1～N7、Canonical Router、反馈、预算、旧兼容与 OpenAPI 的实际受影响测试集合；PostgreSQL 测试只允许单进程串行。
3. 运行 Web 全量单测、TypeScript/生产 build；任何既有失败单列，不以跳过、删除数据或扩大权限换绿。
4. 运行 closure、memory validate、Python compile、`git diff --check`、迁移单头检查；若最后代码无变化，可引用同一 HEAD、同一依赖与同一隔离环境下刚完成的 D6D2 `1280 passed`，但必须记录时间与适用范围。

## 3. 资产控制浏览器卡

- 在三视口 1280×720、1440×900、1920×1080 打开 `/apollo/assets`，完整加载页面后进入“安装管理”，滚动到运行状态区并验证侧栏折叠/恢复、刷新和返回。
- 状态矩阵至少包含：第一代 `uninstalled/stopped` 且运行按钮不可见、第二代 `active/ready/enabled` 且只显示当前允许动作、旧 generation/epoch 不出现在当前 slot；安装 revision/event/Receipt 历史仍可展开读取。
- API/slot 反证由生产 DTO/client/Router 测试与浏览器网络记录共同证明：跨租户、旧代、fenced、Receipt 缺失均不产生可用 slot；页面不得显示“成功”占位或开发编号作为业务标题。
- 浏览器脚本必须保存每视口截图、控制台/page error、500 响应、按钮计数、关键中文状态、请求路径及 PASS/FAIL JSON。若 8434、页面路由或 fixture API 失败两次，停止浏览器动作并先修复服务，不切换控制通道。

## 4. 复审、CAS 与退出

- 回读 D1～D6 文件上限、实际 diff、迁移链、Router 单写、registration-only fallback、no-effect 边界和浏览器结果；独立复审只读，不写 authority。
- 最终 Delivery Receipt/CAS 仅引用本次实际测试、截图、Receipt 和提交 SHA；不把历史计划或 UI 显示当完成证明。
- 退出必须同时满足累计测试、三视口资产控制、closure/memory、无 OCI/临时 schema 残留和 authority 边界复审，唯一结论为 `AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`；随后才进入 AR2-7E，不提前宣布 `AR2_HOST_WIRING_CUTOVER_PLUGGABILITY_BROWSER_ACCEPTANCE_GREEN`。

## 5. 预计文件范围

- 新增本方案、浏览器验收脚本/JSON/三视口截图、累计验证文档和最终 Delivery Receipt/CAS 证据，均位于 `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/`。
- 只有累计或浏览器验证发现确定性缺陷时，才最小修改对应 `services/aos-api` 或 `apps/web` 文件；修改前先在本方案追加具体缺口、文件和退出条件。

## 6. 资产 Registry 累计红项修订卡（2026-09-10）

- 首轮累计为 `851 passed / 16 failed`。十项失败来自 W1/M5 历史测试仍把当前三包送入 legacy `InstallationService.apply/verify`；AR2 已为 domain/growth/niushop 三包声明 runtime，生产 revalidator 正确要求 isolated lifecycle。测试不得关闭该门。
- `m5_bundle_support.copy_and_sign_m5_bundles` 增加显式、仅测试使用的 `declarative_only` 选项；`m5_control_runtime` 固定用它构造版本化 legacy 投影夹具，删除复制品的 runtime 描述与 backend 后再签名。默认 copy/sign 路径继续覆盖当前真实 runtime bundle，D6D2 继续作为当前签名安装的权威联合证明。
- 三项 loader export 失败改为同时接受 manifest exports 与 runtime backend entrypoint 所属目录，仍要求每个声明 export 有制品；boundary 测试从过时的“包内零 Python”改为“可执行源码只能位于 manifest 声明的 backend package，且无网络 endpoint、Secret、SQL/脚本旁路”。候选包含关系检查排除 AR2 新增 backend 与运行缓存，只比较版本化声明资产。
- `asset_registry/control_wiring.py` 当前直接导入 `EcommerceGrowthDisableDependent`，违反通用 Registry 不依赖领域名的既有边界。最小修正为通用 control plane 接收可选 `disable_dependent` 并保存给 runtime host；`main.py` 作为 production composition root 构造具体 ecommerce dependent 后注入。Router 继续从 app state 使用同一 control plane，不产生第二套 service。
- 预计修改：`services/aos-api/aos_api/asset_registry/control_wiring.py`、`services/aos-api/aos_api/main.py`、`services/aos-api/tests/asset_registry/{m5_bundle_support.py,m5_control_support.py,test_m5_ecommerce_bundle_loader.py,test_m5_ecommerce_boundaries.py,test_m5_ecommerce_bundle_contracts.py,test_workshop_module_contracts.py,test_control_wiring.py,test_public_api.py}` 及必要的 startup composition 邻接测试。退出条件为 16 条原失败专项全绿、asset_registry 全量全绿、extension_runtime 邻接全绿、closure/memory/diff check 通过。
- `main.py` 的合法组合根注入会改变 `ar2-1` 当前态精确哈希；只更新 `dynamic-reference-phases.json` 中 `ar2-1` 的该项哈希，保留 `ar2-0` 冻结基线不动。`ar2-7` 当前十项 Router/Web 最终切换红项必须继续保持可见，留给后续受控切换切片消除，不能用本次哈希更新掩盖。

## 7. 资产控制卸载历史解析红项（2026-09-10）

- 浏览器夹具准备回读发现：API `InstallationState`、服务端卸载动作和 Web 动作模型均使用 `uninstalled`，但 `apps/web/src/api/assetControl/installations.ts` 的事件连续性集合缺少唯一合法的 `active:uninstalled`。真实 D6D2 第一代卸载详情会被严格解析器误拒绝，资产控制页无法展示旧审计与零动作终态。
- 最小修复只增加 `active → uninstalled` 合法迁移，并在 `installations.test.ts` 构造完整六 revision 卸载历史正例；另加 `applied → uninstalled` 负例，确保不能跳过 active、disable/detach/resource-release 等服务端权威步骤。前端不自行判断资源已释放，仍只解析服务端已提交历史。
- 修改文件限定为 `apps/web/src/api/assetControl/installations.ts`、`apps/web/src/api/assetControl/installations.test.ts` 及本方案；退出条件为安装解析专项、资产控制相关专项、Web 全量和生产 build 全绿，然后才生成三视口浏览器证据。

## 8. 安装管理正常态刷新红项（2026-09-10）

- 当前安装列表只在错误/空态提供“重试读取”，正常态没有明确刷新入口；无法完成 231-6 的状态变化后刷新回读，也不能用浏览器整页重载冒充产品动作。
- 在 `InstallationPanel` 标题区增加“刷新安装状态”，由 `AssetBundlesPage` 的单一回调依次触发列表、当前已选详情和当前 runtime 的只读 reload；刷新中禁用，未选择详情时对应 hook 保持 idle、不产生伪请求。按钮不触发安装或 runtime command。
- 修改文件限定为 `apps/web/src/pages/s2/AssetBundlesPage.tsx`、`apps/web/src/pages/s2/assetBundles/InstallationPanel.tsx` 和对应现有组件测试；退出条件为组件测试证明回调/禁用行为，Web 全量和 build 全绿，浏览器网络记录证明点击后只有 GET、没有 POST。
