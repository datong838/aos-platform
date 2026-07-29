# W1_DONE — A1 变量页 API 接线

## 改了什么

| 文件 | 变更 |
|------|------|
| `apps/web/src/pages/s2/VariablesPage.tsx` | 接 `GET/POST/PUT/DELETE /v1/modules/:id/variables`；modules 下拉选 module；CRUD 弹层；无后端时 MOCK +「演示路径」条 |
| `apps/web/src/pages/s2/VariablesPage.test.ts` | **新建** 映射/过滤/编解码单测 |
| `services/aos-api/aos_api/routers/modules_variables.py` | `group` 默认 `page`，创建/更新时归一化 page\|app\|global |
| `services/aos-api/aos_api/module_variables.py` | 默认 group `page`；文档注明 scope 约定 |
| `services/aos-api/aos_api/demo/seed_module_variables.py` | seed 用 page/app/global 作 group，覆盖多作用域 |
| `apps/web/src/styles.css` | **仅末尾追加** `/* === W1-A1 === */`（banner / module 选择 / 弹层 / 删除） |

**未改**：CanvasPage、DraftInbox、extras、nav、routes、其他 worker 文件。

## 字段约定

- API `group` ↔ UI 作用域（page / app / global）
- API `varType`（小写）↔ UI 类型（String/Number/…）
- 描述暂作「绑定」列预览；画布真实绑定由 W4 消费同一 API

## 如何自测

```bash
# 前端
cd apps/web && npm test -- src/pages/s2/VariablesPage.test.ts
# → 10 passed

# 后端
cd services/aos-api && python3 -m pytest tests/test_workshop_phase1.py::TestModuleVariables -q
# → 3 passed
```

联调（有 API 时）：

1. 打开 `/workshop/variables`
2. 顶部选 module → 列表来自 API，绿条「真数据源」
3. 新建 / 编辑 / 删除变量后刷新仍在
4. 停后端 → 黄条「演示路径」+ MOCK，本地 CRUD 仍可用

## 风险

1. **group 语义变更**：旧 seed 的「字符串/数值」等中文 group 会被前端 `normalizeScope` 落到 `page`；需重新 seed 才能看到 app/global Tab 有真数据。
2. **绑定列**：API 列表未批量拉 usage，描述作占位；完整「绑定微件」等 W4 画布侧。
3. **未改 Canvas**：画布变量绑定不在本任务范围，Planner 合并后由 W4 只读接同一 API。

## 验收对照（227 · A1）

- [x] 列表来自 API（有后端时）
- [x] module 选择来自 `/v1/modules`
- [x] CRUD 可用
- [x] 无后端 MOCK 降级并标明演示路径
- [x] 不碰 CanvasPage
