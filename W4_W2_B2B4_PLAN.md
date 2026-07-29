# W4 · W2 B2+B4 方案（Studio 40→65 · Publish 50→65）

> 分支：`feature/223-worker-4` · 基线 `ad2241a`  
> 依据：`227-未完成项补齐计划.md` W2·B2+B4（**本波不做 B5**）  
> 原则：最小改动；不翻修视觉；不碰他人页面 / nav / main.py（除非 publish 完全不可用）

## 1. 验收对照

| 任务 | 目标 | 本波动作 |
|------|------|----------|
| **B2 Studio** | ≥2 Tab 可写配置并保存 | 提示词 Tab + 工具箱 Tab 可编辑并保存 |
| **B4 发布** | 环境卡 + 步骤与 `POST /v1/modules/:id/publish` 一致 | 模块选择、4 环境卡、步骤条、成功/失败态 |

## 2. B2 · StudioPage

### 2.1 可写 Tab

| Tab | 可写内容 | 保存路径 |
|-----|----------|----------|
| **提示词** | `systemPrompt` textarea +「保存提示词」 | 优先 `PUT /v1/aip/agents/:id/prompt`；404/失败 → `localStorage`（角标：**演示路径 · localStorage**） |
| **工具箱** | 工具启停勾选 +「保存工具配置」 | 优先 `PUT /v1/aip/tools/config`（categories 由已启用工具推导）；失败 → 同 agent 的 localStorage（角标演示路径） |

试运行 / 发布 Tab：保持现有只读/门控示意，不在本波加深。

### 2.2 纯函数（可测）

从 `StudioPage.tsx` 导出：

- `studioPromptKey(agentId)` / `loadLocalPrompt` / `saveLocalPrompt`
- `studioToolsKey(agentId)` / `loadLocalTools` / `saveLocalTools` / `toggleToolId`
- `toolsToCategories(enabledIds, catalog)` — 映射到 tools/config categories
- `formatStudioSaveMsg(path, ok)` — 成功/失败文案

### 2.3 不动

- 不大改布局/视觉；左侧 Agent 列表保留静态壳（可切 activeId）
- 不改 `AgentsPage` / `nav.ts` / `main.py`

## 3. B4 · PublishPage

### 3.1 UI 补齐

1. **模块选择**：`GET /v1/modules` → select；无模块时允许「新建并发布」走现有 POST create
2. **步骤条**：开发 → 测试 → 预发布 → 生产（四态：done / current / pending）
3. **环境卡**：四环境卡片，展示最近部署状态（`GET /v1/modules/:id/deployments`，无则 pending）
4. **发布**：对选中模块 `POST /v1/modules/:id/publish`（Idempotency-Key）；成功后再 `POST .../deploy` 写入目标环境（已有 deployments API，不改 main）
5. **成功/失败态**：明确 banner（绿成功 / 红失败），展示 moduleId、channel、publish.status、幂等

### 3.2 环境映射

| UI | channel / environment |
|----|------------------------|
| 开发 | `dev` |
| 测试 | `test` |
| 预发布 | `staging` |
| 生产 | `prod` |

（替换现有 rc/beta/stable/hotfix radio，与 checklist §7.5 一致。）

### 3.3 后端（可选最小）

- **优先不改**：`publish` 响应已有 `publish.channel`（固定 `dev`）；前端以所选环境为主展示，deploy 写真实 environment。
- **若必须**：仅在 `modules.py` / `module_store.publish_module` 接受可选 `channel` body 字段回写响应——**本波先不改**，靠 deploy environment 对齐。

### 3.4 纯函数（可测）

- `PUBLISH_ENVS`、`envStepIndex`、`stepState(i, current)`
- `pickLatestByEnv(deployments)`、`formatPublishResult(...)`

## 4. 文件边界

| 文件 | 改动 |
|------|------|
| `apps/web/src/pages/StudioPage.tsx` | B2 可写保存 |
| `apps/web/src/pages/StudioPage.test.ts` | 新建纯函数测 |
| `apps/web/src/pages/PublishPage.tsx` | B4 环境卡/步骤/选择/态 |
| `apps/web/src/pages/PublishPage.test.ts` | 新建纯函数测 |
| `apps/web/src/styles.css` | 末尾仅追加 `/* === W2-B2B4 === */` |
| `W4_W2_DONE.md` | 交付说明 |

**禁止**：AipAnalyst / Observability / Capacity / ModelCatalog / CapabilityPage / nav.ts / push / 改 m1 / merge / B5 插件。

## 5. 风险与回滚

| 风险 | 缓解 |
|------|------|
| agents 引擎无预置 Agent → prompt PUT 404 | 明确演示路径 fallback，不阻断保存 |
| tools/config 为全局配置 | Studio 仅写入 categories；失败则 localStorage；不删他人字段 |
| publish 硬编码 channel=dev | UI/deploy 以所选 env 为准；响应 channel 仅作参考展示 |
| 改动影响现有 publish 幂等演示 | 保留 Idempotency-Key 二次调用校验 |

回滚：还原上述 4 个页面/测试 + CSS 段 + 本方案/DONE 即可。

## 6. 自测清单

1. `/aip/studio` → 提示词改文案 → 保存 → 见成功角标（API 或演示路径）
2. 工具箱勾选切换 → 保存 → 刷新后启停态保留（local 或 API）
3. `/workshop/publish` → 选模块 → 选环境卡 → 发布 → 成功态含 status=ACCEPTED
4. 断网/错误 → 失败态红条可见
5. `pnpm test`（StudioPage + PublishPage）通过
