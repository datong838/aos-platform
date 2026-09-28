# W5CB4 BG-00g｜SkillBinding 评估与激活产品接线文件级方案

## 上位合同与现场

复习 `231-工作台业务闭环长程开发路径与波次实施计划.md` 的 A1 首链和安装≠启用语义、`231-1` 四层与首链依赖、AIP-6 BIND-3。现有 `routers/aip_bindings.py` 已有只读语义的 `/skill-bindings/preview`、持久 `/{id}/evaluate` 和 `/{id}/activate`；`AipSkillRegistry` 对 evaluate 做 version CAS、预算绑定不变、精确依赖解析，对 activate 做新鲜 readiness/依赖重算与 version/status CAS。当前 D01@1 仍 evaluated、当前库 Binding/CapabilityBinding/RuntimePolicy 等正式来源为空，不能在当前实例提交写命令。

## 文件级 RED 与最小实现

1. 先在 `apps/web/src/api/aipAgentControl/skillBindingLifecycle.test.ts` 写 RED：无 Binding、跨租户、非 provisioning/suspended、无精确依赖来源、错 budget、过期 readiness、错 version/hash 时禁入；preview 只返回当前依赖快照，不能当作已评估；evaluate/activate 必须一次不排队命令、同租户 Binding 与 Receipt 精确回读；未知结果保留原 idempotency key 并仅只读对账，不换键重发。
2. 最小新增 `apps/web/src/api/aipAgentControl/skillBindingLifecycle.ts`。从同租户 exact Binding、published Skill、当前 ModelRoute/RuntimePolicy/EvalGate 和原 Owner 能读取的许可、数据、工具、预算来源编译 `OperationalBindingDependencies`；缺任一正式来源即返回 blocker，禁止自由文本与默认引用。对 `/preview`、`/evaluate`、`/activate` 按原 DTO 请求；evaluate 使用 `expectedVersion`，activate 使用现版与 `expectedDependencySnapshotHash` 且客户端预检 readiness available/未过期，Owner 在事务内再重验。每次命令先记持久未决标记，成功必须回读 Binding + Receipt；失败/未知不重发。
3. 在 `apps/web/src/pages/s2/SkillBindingCreatePanel.tsx` 或独立最小组件接已存在 Binding 的显式评估、激活步骤；`CanonicalAgentRegistryPage.tsx` 只显示当前精确 Binding 的状态、缺口和人工确认。当前 D01 evaluated 不出现可执行动作。测试使用隔离 fixture 验证代码，不把 fixture 当正式来源。
4. 专项与相邻页面累计、TypeScript、diff check；适用时 browser-pilot 截图。真实库只读检查 Binding/Receipt/Host 仍 0；无正式 Eval/预算/能力来源不进行当前 POST，不启 Host/worker。

## 重启边界

用户将重启电脑。本文件仅冻结下一刀方案；重启后先复核 m1 单写者、当前权威数据卷、备份、DB 迁移、PG/API/Web 及页面，再 RED/编码。若服务进程中断，按每日 09:00 同级检查门恢复，但不可将 200 视为业务链完成。
