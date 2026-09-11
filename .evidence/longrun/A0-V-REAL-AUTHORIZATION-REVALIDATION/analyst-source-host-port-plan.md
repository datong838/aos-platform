# 经营参谋分析来源宿主端口实施方案

日期：2026-09-11
基线：`m1@8f0640fb`

## 目标

把 growth 包已经完成的分析来源材料合同，接到宿主唯一拥有的
`EvidenceBundle`、`TaskBrief`、`EvidenceDisclosureDecision` 与数据库事务读取上。
包只接收宿主返回的材料并做第二次完整性校验；包不得获得原始数据库连接、
不得自行决定租户、披露、freshness、revocation 或 marking，也不得产生任何写入。

## 当前输入与 preHash

| 文件 | preHash |
|---|---|
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/sdk_ports.py` | `8a213388e3594e6735868566b2449cac12dcd8ddeeeea372bed8c69925bcc151` |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_analysis_sources.py` | `c9b546c3b61d79694e39b0cfc821c4fa7e098d7e648208746b8b6fb7e2998583` |
| `services/aos-api/aos_api/ecommerce_analyst_analysis_sources.py` | `e3b2bec141e929e2c7aa6d69227cf7c042359be744caa1ba129c54b8bc10467a` |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `2eded263cb3689e259552cac3bdd81b3e479b079691913e89866f994de7c6867` |

新文件：

- `services/aos-api/aos_api/ecommerce_analyst_analysis_source_port.py`
- `services/aos-api/tests/extension_runtime/test_ecommerce_analyst_analysis_source_port.py`

## 最小实现

1. 在 growth SDK 增加只读 `GrowthAnalysisSourcePort`。端口不接受租户参数，租户由宿主构造端口时绑定。
2. 在 growth 分析来源模块增加单次 `read_authorized_analysis_bundle` 编排：严格校验调用参数，调用端口一次，并复用现有材料完整性校验。
3. 新增宿主绑定实现，只持有 `HostTransaction` 与 `TenantScope`；将秒数上限转换成 `timedelta` 后调用既有 `read_analysis_bundle` Owner 读取。
4. 不增加 HTTP 路由、operation 注册、Provider 调用、Receipt、写事务或真实租户激活。

## 不变量与失败关闭

- 调用方不能提交或覆盖 `orgId/projectId`；宿主绑定的 `TenantScope` 是唯一租户来源。
- 包看不到原始连接，只能调用一次只读端口；端口异常不重试。
- `taskId`、actor、marking、时间、来源最大年龄、总字节数都必须显式且有界。
- 宿主先做真实 Owner、完整授权与时效校验；包再校验 exact ref、payload hash、披露身份/过期时间、全量覆盖与字节上限。
- 本切片无副作用，不宣称 A0-V、真实首链或分析生成已经完成。

## 验证与退出条件

1. 包测试证明参数原样规范化转发、宿主顺序保持、异常不重试、非法输入调用前拒绝。
2. 宿主测试证明只传入 `HostTransaction`，租户不能覆盖，边界参数调用前失败。
3. 既有宿主 Owner 测试、分析结构测试和包边界测试全部通过。
4. `verify_closure.py --phase ar2-7` 通过，新增包模块不依赖 `aos_api`、数据库或 I/O。
5. 逐文件证据、最终 hash、验证结果写入证据目录并更新清册后，单独提交到 `m1`；不 push。
