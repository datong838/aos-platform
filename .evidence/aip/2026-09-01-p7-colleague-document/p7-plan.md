# AIP P7 六数字同事与文档智能跨页闭环施工方案

## 目标

在不降低租户、安全、审批、Receipt 与外部副作用门禁的前提下，把既有原子 Skill、版本化 Logic、六数字同事与 Workshop 八页面连接为业务人员可理解、可操作、可回读的闭环；同时把文档智能从“上传/抽取页面”补齐为有来源、模板版本、置信度、人工复核、谱系与下游交付的受治理工作流。

## 上位约束

- 六数字同事是 `AgentTemplate + ResponsibilityProfile + SkillBindingSet`，不是六个大 Skill。
- 用户入口按“原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献视图”呈现。
- Workshop 是业务问题空间；AIP 页面负责治理、绑定、证据和跨页追溯，不复制业务事实权威。
- 真实租户仅 `org-org/dev-project`；`dev-org/dev-project` 仅做隔离验证。
- 不调用 Provider、不解析 Secret、不创建真实业务副作用、不切生产路由、不迁移、不发布。

## 文件级波次

### P7A：六数字同事公共业务闭环（AIP-P7-114～120）

1. `apps/web/src/components/aip/colleagueBusinessLoops.ts`
   - 冻结六角色中文业务输入、业务产出、工作台贡献目标和回读入口。
   - 只接收服务端返回的精确 Logic 标识与运行状态，不在前端伪造就绪。
2. `apps/web/src/components/aip/ColleagueBusinessLoopCard.tsx`
   - 展示“业务输入→已版本化 Logic→数字同事产出→工作台贡献→结果回读”。
   - 技术标识折叠为审计信息；主视图只呈现中文业务语义。
3. `apps/web/src/pages/s2/CanonicalAgentRegistryPage.tsx`
   - 在六角色目录卡中接入公共业务闭环。
   - 工作台链接携带角色上下文，且提供结果回读入口。
4. `apps/web/src/components/workshop/TaskCockpitPage.tsx`
   - 读取角色上下文，定位对应数字同事并保持返回目录的路径。
   - 不创建演示任务；正式任务仍只来自服务端。
5. 对应测试：
   - 六角色完整且不重名；每角色均有输入、产出、工作台和回读。
   - Logic 只来自权威回包；缺失时显示“需核验业务逻辑”，不填造编号。
   - 工作台深链可定位角色，返回链接保持可用。

### P7B：文档智能治理闭环（AIP-P7-121～124）

1. `services/aos-api/aos_api/routers/phase6_documents.py` 与关联权威合同/存储：
   - 补齐租户、来源、文档类型、字节数、敏感级别、保留策略、模板版本、运行证据、谱系与 Receipt。
   - OCR/抽取进度、页码、置信度、错误、用量和安全重试以服务端回包为准。
2. `apps/web/src/pages/s2/DocumentIntelligencePage.tsx`：
   - 本地预览与服务端接收分离；上传成功只能由服务端 Receipt 证明。
   - 支持来源对比、人工修订、复核、导出、回滚到模板版本和下游 Task/Logic 交付。
   - `AipAssistPage.tsx` 与 `LogicCanvasPage.tsx` 必须消费文档交付上下文但不得自动创建 Task/Logic；返回文档页时按精确 `documentId` 重新定位。
3. 严格 API parser/client 与专项测试：未知字段、跨租户、模板漂移、缺失谱系或 Receipt 均失败关闭。

## 验证矩阵

- 前端专项：六角色闭环、目录深链、工作台角色定位、文档上传/抽取/复核/导出。
- 后端专项：文档合同、租户隔离、状态机、模板版本、Receipt 与谱系。
- 累计回归：P7 相关 AIP/Workshop 测试、TypeScript、Vite build、diff check。
- 浏览器：内置浏览器逐个点击六角色入口与返回；文档页完成至少一条无外部副作用的本地开发流；检查控制台、滚动区、侧栏完整性和空态。
- 数据：`org-org/dev-project` 只读回读；`dev-org/dev-project` 负向隔离。

## 风险与回滚

- 风险：前端静态角色说明与服务端角色目录漂移。控制：角色键集合严格校验，Logic/状态仅取服务端。
- 风险：把本地文件选择误报为上传成功。控制：只在服务端返回文档/Receipt 后进入已接收态。
- 风险：文档抽取触发未知 Provider。控制：本波不新增 Provider 调用；缺少权威运行证据时保持需核验。
- 回滚：P7A 为加法式组件与深链，可独立撤回；P7B 采用加法式合同字段和显式兼容解析，不删除现有文档记录。
