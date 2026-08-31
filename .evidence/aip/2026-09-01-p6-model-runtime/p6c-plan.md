# P6C 容量、成本与用量权威闭环施工方案

## 上位方案复核

- 以 164 总控 P6-106～P6-109 为验收边界：用量只认租户内 Usage Receipt，成本只认成本凭证及调整，容量只认 exact CapacityPool。
- 遵守“原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献视图”的解释链，但在当前 Usage Receipt 没有相应归因时保持缺证，绝不把缺证渲染为 0。
- 本波不调用 Provider、不改真实业务数据、不切生产流量、不发布；所有写入控件继续走安全预检与精确重读。

## 现场缺陷

1. 用量卡片仍读取旧 `/v1/aip/capacity/usage`，空列表会被聚合成今日/周/月全 0，不能区分“无调用”与“缺少 Usage Receipt”。
2. 用户限制表把不存在的日预算、今日已用强制映射为 `$0` 和 `0%`。
3. 预留容量页存在静态 `20%` 与“未开通”占位，没有消费 exact CapacityPool。
4. 容量池没有展示并发、用量单位、租约、生命周期和超限处置入口。
5. 浏览器实测发现限速表把池总上限 `maxTokenUnits` 误写成“每次租约”用量，必须改为 `tokenUnitPerReservation`，避免把总容量冒充单次占用。

## 串行拆分

- P6C-A：先闭合真实周期 Receipt、缺证语义、exact 容量池及安全处置入口；这一提交只声明 P6-108、P6-109 闭合。
- P6C-B：继续补齐 Agent/Logic/模型/任务归因，以及 RPM/TPM/并发/预算的版本化配置、CAS 冲突和精确重读；P6-106、P6-107 在该子包证据闭合前保持未完成。

## 文件级施工清单

- `services/aos-api/aos_api/aip_model_runtime_contracts.py`：补充 Usage Receipt 的按周期/种类/供应商可解释汇总合同。
- `services/aos-api/aos_api/routers/aip_model_runtime.py`：只从租户域 Usage Receipt 与 Adjustment 生成今日/近 7 天/近 30 天汇总。
- `apps/web/src/api/aipModelRuntime/contracts.ts`、`parser.ts`、`parser.test.ts`：补齐严格解析与计数一致性校验。
- `apps/web/src/pages/s2/CapacityPage.tsx`、`CapacityPage.test.ts`：去除缺证归零与静态预留占位，改用权威汇总和 exact CapacityPool。
- `services/aos-api/tests/aip/test_aip_model_runtime_api.py`：覆盖无凭证、真实凭证、周期汇总、调整和租户隔离。

## 退出条件

- 专项前后端测试、TypeScript、生产构建全部通过。
- 内置浏览器逐个点击用量、限速、预留三个页签，确认控件可工作且没有静态假值。
- 形成 P6C 验证证据、Delivery Receipt、安全提交、authority CAS、memory sync/validate/gate 与 Prime 回读。
