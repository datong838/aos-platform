# W5CB2-P2b｜exact 内容命令预检与 Journal hash 修复阶段验证

- 基线 `053bd986`；P2a 已提供唯一批准事件与原批准金额。P2b 仍不是 W5CB2 终态，也不授权生产 Worker/Provider。
- `ContentBudgetCommandOwner._build_command` 从 pending 意图、Review Receipt、安装/Dispatch 组、当前 Plan/AgentRun、Route/价格/Quota/Budget、容量和批准事件构造唯一 `content.generate` envelope，并在 claim 前调用正式 `ContentGenerateHostService.revalidate`。事实来源仍来自已批准 `sales_weapon_method.evidence_refs`；金额仍来自原 approved ActionDraft。缺失或旧代禁入。
- Host envelope 与可插拔 bundle 的 `ContentCapabilityRequest.command_payload()` 逐字段和 requestHash 对照；API 生产模块不导入 bundle 或未安装的 SDK。`claim` 仅在完整预检后调用 `a0v_104` 一次，再用独立读事务确认 claimed/attempt=1/token；未知结果不自动重试。
- 发现并修复 `ContentExecutionJournal.list_held` 的真实阻断：正式 Runtime Receipt 的 request_hash 是含内层 `requestHash` 的**完整命令 hash**，原代码误比对内层 hash，导致真实 HELD/PENDING 消费被拒。修复只改此比较，与 `a0v_104` ack 的完整 hash 条件一致。
- RED：Host/bundle 同形测试先因 envelope helper 缺失失败；缺意图测试先因预检方法缺失失败；claim 测试先因方法缺失失败；Journal 完整 hash 测试先因旧比较失败。GREEN：Owner 7/7，邻近合计 37/37，Journal hash 1/1；compileall、`git diff --check` 通过。浏览器不适用（无页面变更）。
- 风险/未验：成功预检测试的 Route/批准/安装是受控夹具，不是完整同库 Handoff→容量→预算；Host commit、提交后 HELD+PENDING+Receipt 独立读回、ack、默认关闭 Worker 接线和真实实例均未完成。不能声称已预留预算、调用模型或产出内容。
- 立即下一段 W5CB2-P2c：在 claimed token 下重新预检、单次正式 capability Host commit、独立三表读回后 ack；补 Host unknown/并发/跨租户 PG 拒绝，累计回归和同库一体夹具。P2 完整 verification 与 D-waves/AOS/Prime 同步仍待最终退出门。
