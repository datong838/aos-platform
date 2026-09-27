# W5CB4 当前新实例 Runtime 配置权威波计划（2026-09-27）

- 上位方案复习：231 主计划 BG-00/A0-V 要求产品 UI 完成获准配置，签名/Registry/approved 安装只到前置，不可把脚本填库当产品入口；231-9 首链的权限、预算、审批必须 exact。当前 HTTP 预览波 `m1@a8e679f7` 新实例 `approved`、Runtime binding=0，八类正式配置计数全 0；原库 `a0v_092` 不动。
- 文件级清单先限只读：`scripts/a0v_canonical_ecommerce_first_install.py` 的配置门查询；责任计划、RuntimePolicy、GuardPolicy(data/egress)、NetworkPolicy、ModelGovernancePolicy(quota/budget)、BudgetRevision 的公共 Store/Router 与相应前端设置入口；形成每类“创建/激活/失效/预算单位/安装代次引用/当前权限”的矩阵。方案与证据放本目录，不先造政策数据。
- 随后分切片实施最小产品入口缺口：先让 approved 安装在 UI 显示八类具体阻断和正式配置导航，保持旧页面正常功能；再依正式 Owner 逐类配置、专项与累计回归、浏览器验收，最终三 Runtime apply/verify/configure/enable 后才可切 8080 预览。每切片单独 verification/m1 提交。
- 当前不会为八类空权威编造默认策略、预算或真人审批；无商城源读、无旧 Run replay、无 Provider、无原库迁移。此配置波与不依赖新实例的 P2g30b RETURN exact Action 生产者可串行交替，避免配置等待拖慢首链代码。

## 首切片：只读 Owner／UI 差距矩阵

- 本切片只查现有 Store、Router、Web 调用点和当前安装，不改运行状态。输出八类各自的正式写入口、前端可操作性和缺口；先冻结下一切片的具体文件清单。
- 验收：当前安装/签名/数据库仍 exact，配置空缺不被“补绿”；矩阵可指导下一切片只加只读阻断说明与导航。核验文件落盘并独立提交后，本配置波的下一切片才写代码。
