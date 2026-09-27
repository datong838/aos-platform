# W5CB4 E03：首链正式配置生产者最小切片审计计划（2026-09-28）

## 上位与目标

231/231-9 的 A1/BG-00～04 要求真实可配置的六角色与自然首链，不靠开发者手工串 Run。当前卷已备份、迁 a0v_107 并以最新代码重启；E01 发布页面只读候选确实 0。E03 不扩大到全 37 Skill 或旧快照；只为 D01→C03 首链找出下一个**可合法生产的最小正式来源**，并把无法由研发凭空补的凭证/业务审批列出，不做假绿。

## 串行清单

1. 复习产品方案、231-9 第 2/3/7/8 节及当前 m1 代码；只读核当前租户 LogicGraph/Publication、ReleaseGate/Event、ModelRoute/Policy、Skill/CapabilityBinding、Provider 等数量和生命周期，不读取商城源库。
2. 逐一核已有正式 Owner 与产品入口：`LogicCanvasPage.tsx`/`aip_logic_graphs.py`/`aip_logic_publications.py`，`ModelRuntimePage.tsx`/模型路由 Owner，`phase3_aip_skills.py`/`aip_bindings.py`；核 signed growth bundle 的 37 Logic 目录是不是可执行 Graph，而非把 catalog 名称伪装成 Graph。
3. 画一条首链最小依赖链，分别标“已有可操作入口”“需编码的生产者”“真实凭证/审批门”；首选能不接外部 Provider、不造业务批准、但能让后续 Skill/Logic 正式来源发生的单文件级切片。若本波只审计，提交 verification 后立即开 E04 实现。
4. 做只读当前库/HTTP/浏览器核验、方案一致性与风险复审；verification→m1 commit→AOS/Prime 上下文必要更新→自动 E04。Host/worker/Provider 继续关闭，不调用业务 POST。

## 停止条件

如果只有 catalog 描述没有可执行 Graph，不能自动发布 Logic；若模型路由需要未提供的外部 Provider 凭证，不伪造健康/价格/预算。未知结果不重发、旧 12 Run 不重放、不删数据。审计必须有明确下一编码目标，不停在泛泛缺口清单。
