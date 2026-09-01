# P6D 模型运行全链与累计封板施工计划

## 1. 上位方案与边界复核

- 总控任务：`164-AIP全菜单业务可用性缺陷总控与分批整改清单.md` 的 P6-110～P6-113。
- 当前 authority：`AOS-000444`，P6C-B 已完成；强一致投影与 memory gate 已恢复 GREEN。
- 真实租户仅用于只读验收：`org-org/dev-project`；写入性浏览器验收只允许使用 `dev-org/dev-project` 隔离 canary。
- 本波不解析或展示 SecretRef 正文，只显示 secret backend、精确版本与是否已绑定。
- 本波不调用 Provider、不做预热、不发送试聊、不产生真实业务写、不迁移、不发布。只有同一截止面的路由、模型、供应商、策略、评测、健康、容量全部 GREEN 时，页面才显示“允许进入受控试聊”，否则保持关闭并给出可执行复核动作。

## 2. 当前缺口

1. `ModelRuntimePage` 只分别列出资产摘要，不能按路由串成 Provider→SecretRef→Policy→Eval→Health→Capacity 链。
2. 失败链路只有聚合 blocker code，缺少节点级截止时间、影响对象、责任入口和复核动作。
3. 用量投影已有 task/agent/logic/model 五维汇总，但运行页没有提供任务到模型、模型到数字同事/业务逻辑的可审计反查。
4. 页面没有清晰区分“运行链已满足”与“允许进入受控预热/试聊”；容易把控制面配置误解为外部调用已经成功。

## 3. 文件级最小施工

### 后端

- `services/aos-api/aos_api/aip_model_runtime_contracts.py`
  - 增加 Secret-free 的运行链节点、影响摘要和逐路由链 DTO。
- `services/aos-api/aos_api/routers/aip_model_runtime.py`
  - 在既有 overview/cost authority 上构建租户内逐路由链；使用精确 revision/hash 关联模型、供应商、策略、评测、健康与容量。
  - 失败节点给出 observed/expires、影响对象、owner route 与 recheck action；不得把缺失解释为 0 或成功。
  - 使用 usage receipt/attribution 的同 lineage 关系生成任务→模型和模型→Agent/Logic 反查；没有精确相关证据时明确返回空，不做推断。
- `services/aos-api/tests/aip/test_aip_model_runtime_api.py`
  - 覆盖 ready/blocked/expired/missing、租户隔离、无 SecretRef 泄漏、同 lineage 影响反查与无证据可信空。

### Web

- `apps/web/src/api/aipModelRuntime/contracts.ts`、`parser.ts`、`index.ts`、`parser.test.ts`
  - 增加严格解析的运行链/影响 DTO 与 API client；拒绝不完整 ready 合同和凭据字段。
- `apps/web/src/pages/s2/ModelRuntimePage.tsx`、`ModelRuntimePage.test.ts`
  - 以逐路由链替换仅有聚合摘要的主阅读路径。
  - 每个节点显示中文状态、截止时间、影响对象、责任入口、复核按钮/动作。
  - 显示任务→模型→数字同事/业务逻辑反查；无证据时显示可信空。
  - 仅当 `controlledTrialAllowed=true` 时显示“进入受控试聊”，本波不自动调用；否则解释关闭原因。

## 4. 验收

1. 专项 backend pytest 与 frontend parser/page tests。
2. P6 累计后端回归、Web P6 五页累计回归、`tsc --noEmit`、production build。
3. 内置浏览器分别验收真实租户只读链和隔离 canary 可信空/阻断链，确认无 SecretRef 正文、无 Provider 请求、无业务写。
4. 复核方案、代码、测试与页面文案一致；更新 P6-110～P6-113、verification、Delivery Receipt、commit、authority CAS、memory sync/validate/gate 与 Prime 回读。
