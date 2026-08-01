# 228 · Wave 3B W2 AIP 四页真实性闭环实施方案

> 基线：`1663bba`
> 范围：Observability、Capacity、Model Catalog、Studio 及其专项测试；Studio 最小扩展 AIP agents router/engine
> 上游：`228-W3B-P1主流程交互真实性闭环方案.md`、`228-227页面交互真实性全量审计与修复方案.md`

## 1. 使用 Rules

1. 四阶段固定按 Observability → Capacity → Model Catalog → Studio；每阶段先补失败场景测试，再最小实现并回归所有前序阶段。
2. live GET 的空数组就是真实空态；请求失败显示当前 Tab/资源错误，不得回填成可写 MOCK。
3. 写请求冻结目标和草稿，严格校验响应目标与关键字段，再 GET 同一资源重读；只有重读一致才清理 dirty 并显示成功。
4. 写失败保留草稿；写成功但重读失败或不一致显示“写入已提交但重读核验失败”，不得误报保存失败或保存成功。
5. 没有统一后端契约的操作禁用或只读；不使用 React state、localStorage、全局 tools/config 或模型注册冒充生产持久化。
6. 只修改 W2 独占页面、测试和 `phase3_aip_agents.py`、`aip_agents_engine.py`、对应测试；不改路由聚合、共享 API client、全局 CSS、OpenAPI。

## 2. 阶段一：Observability

### 2.1 数据与交互

- Overview、Traces、Metrics、Alerts 按 active Tab 独立请求；失败只影响当前 Tab。
- Overview/ Metrics 复用 `/v1/aip/observability/summary`；Token 标“估算”，trend 标“采样推演”。
- Traces 只展示 `/v1/aip/observability/traces` 的采样路由统计；没有 span API 时不渲染 MOCK waterfall。
- Alerts 使用 `GET /api/aip/alerts`，从 `config` 读取 severity/firedAt/value；确认/静默使用 `PUT /api/aip/alerts/{id}`，校验 id/status 后重新 GET 列表确认。
- Dashboards 的 Add Widget 禁用并标“持久化契约规划中”。Export 只导出当前 Tab 展示的数据及 `source/range/generatedAt`。

### 2.2 测试

- live 空 summary/traces/alerts 不注入 MOCK。
- 某 Tab 失败不污染已成功 Tab。
- Alerts 覆盖响应 ID/状态错配、写后 GET 不一致、写成功但重读失败与成功重放。
- waterfall 与 Add Widget 禁用不产生请求；导出内容对应当前 Tab。

## 3. 阶段二：Capacity

### 3.1 数据与交互

- 初始分别读取 usage、project limits、user limits；空数据保持空态，失败不回填 MOCK。
- 项目管理编辑 `rpmLimit/tpmLimit`，PUT `/v1/aip/capacity/project-limits`，校验 `scope=project`、`scopeKey`、RPM/TPM，再 GET 同 scope 重读。
- 用户管理冻结 `userId`，PUT `/v1/aip/capacity/user-limits?userId=...`，以相同规则校验并 GET 同用户重读。
- Cancel 恢复最近一次服务端快照；写失败与核验失败保留草稿。
- team、daily budget、per-model limits、reserved capacity 均只读，并明确 API 未支持。

### 3.2 测试

- 项目/用户保存覆盖成功、回包 scope/target/数值错配、重读失败与重读不一致。
- Cancel 恢复服务端快照；失败保留输入值。
- 无用户 key 时保存禁用；per-model/预留容量不发写请求。
- 每完成本阶段回归 Observability + Capacity。

## 4. 阶段三：Model Catalog

### 4.1 数据与交互

- live 目录和已注册列表为空时显示真实空态，不补 MOCK；API 故障可展示显著 demo 目录，但注册按钮禁用。
- POST `/v1/aip/model-catalog/{id}/register` 必须校验 `ok=true` 且 `item.modelId` 与目标一致，再 GET `/v1/aip/registered-models` 确认目标存在。
- POST 成功但 GET 失败/缺少目标时显示独立核验失败文案；不得提前把卡片改为已注册。
- Settings 与 Enablement 无组织 enrollment/法律启用契约，Toggle、取消、保存、管理全部只读/禁用并说明。

### 4.2 测试

- live 空目录/空已注册列表、demo 禁止注册。
- 注册覆盖 `ok`/modelId 错配、重读失败、重读缺失与成功闭环。
- Settings/Enablement 禁用按钮不产生请求。
- 每完成本阶段回归前三阶段。

## 5. 阶段四：Studio

### 5.1 后端最小契约

- 新增 `POST /v1/aip/agents`，接受 name/description/source/tags/status/system_prompt，返回创建后的完整 Agent。
- 新增 `PUT /v1/aip/agents/{id}/tools`，接受 agent-scoped ToolRef 列表，返回 agent_id/items/count；engine 保存后原 GET 可重放。
- Prompt PUT 回包补 `agent_id`，供前端严格核对；不触碰共享路由聚合/OpenAPI。

### 5.2 前端数据与交互

- `/v1/aip/agents` 是唯一 Agent 列表真源；空列表显示真实空态，失败不回填硬编码 Agent。
- Prompt GET 作为服务端快照；PUT 校验 agent_id/prompt 后 GET 重读，一致才成功。失败不写 localStorage。
- Tool 目录读取 `/v1/aip/tools`；Agent 分配读取/写入 `/v1/aip/agents/{id}/tools`，不再调用全局 `/v1/aip/tools/config`。
- 共享 CreateAgentWizard 的工具 ID/模型 fallback 语义不能安全对齐本波契约，因此“新建智能体”禁用并说明；后端 POST 先以 API 单测锁定，后续再协调向导。
- Try chat 失败保持失败且不显示伪答案；Publish 的 87% 改为“示意数据、只读”。

### 5.3 测试

- Agent 列表覆盖真实空、加载失败、选择切换与旧请求隔离。
- Prompt/Tools 覆盖写后重读、响应错配、写成功重读失败、失败保留草稿。
- 新建禁用、Try chat 失败不显示示意答案、Publish 明确示意。
- 后端覆盖 POST 创建、Tools PUT→GET 重放、缺失 Agent 404、Prompt agent_id。
- 每完成本阶段回归四页专项。

## 6. 最终门禁与残余风险

1. 最终执行相关 AIP agents 后端测试、Web 四页专项、Web 全量、TypeScript typecheck、Python compile、`git diff --check`。
2. Observability 仍是进程采样与路由聚合，不是完整分布式 tracing。
3. Alerts 与 Agents 当前引擎为进程内状态；本波只按现有契约完成刷新重放，不宣称服务重启持久化。
4. Studio 新建 UI 因共享向导契约未协调保持禁用；后端 POST 已就绪但不伪造可用入口。
5. Model enrollment、Dashboard Widget、团队/预算/per-model Capacity 继续等待统一后端契约。
