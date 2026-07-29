# W2 · W4-C8b 方案：Action 详情可视化/布局（55%→70%）

## 1. 目标

对照 `223-deep-checklist-3` 页面 3（Action 详情）与视觉稿 `ontology-action.html`，在 **不破坏现有 CRUD + 试跑** 的前提下，补一块高价值可视化，将完整度从 **55% → ~70%**。

本波只做「有价值的一块」，不做 Dependents 全量、不改导航/main、不碰 Link/Capability/DocIntel。

## 2. 现状与差距（摘）

| 项 | 现状 | 本波是否做 |
|----|------|------------|
| 左栏 8 段导航 + 状态流水线 + CRUD/试跑 | ✅ 已有 | 保持 |
| Action overview：Input + Rules 双列 | ❌ | **做** |
| 参数可视化表（非纯 JSON） | ❌ 仅 textarea | **做**（表 + JSON 并存） |
| Rules 类型徽章（Create/Modify/Delete/…） | ❌ | **做** |
| Dependents 7 类卡 | ❌ | 不做（下一批） |
| RID / Tool desc / Contributors 全量信息表 | 部分 | 轻量补 RID 派生展示，不扩库 |

## 3. 方案设计（最小改动）

### 3.1 前端纯函数（可单测）

在 `ActionTypeEditorPage.tsx` 导出：

- `deriveActionRid(id)` → `ri.actions.main.action-type.{id}`
- `parseJsonArraySafe(text, fallback)` → JSON 解析失败回落，保证可视化可降级
- `buildOverviewInputs(parameters)` → Input 列条目 `{ name, type, required, desc }`
- `buildOverviewRules(criteria, objectType, remoteRules?)` → Rules 列条目  
  - 优先用可选远程 `/v1/action-rules?action_type_id=`（已有 router，**不改 main.py**）  
  - 失败或空时：由 `submissionCriteria` 推导（`op`→徽章 kind：`required`/`eq`→Modify 语义徽章，缺省 `Action`）
- `ruleKindBadge(kind)` → Create / Modify / Delete / Link / Action 徽章文案与色类

### 3.2 UI 落点

1. **Overview** 区块增加 `at-overview` 双列：
   - 左 Input：参数列表（类型徽章 + required 标记）
   - 右 Rules：规则流（kind 徽章 + 目标 OT badge + 条件摘要）
2. **Parameters** 区块顶部增加参数表（name / type / required），下方保留 JSON 编辑与试跑（行为不变）
3. **Rules** 区块顶部增加规则流预览，下方保留 criteria JSON

编辑 JSON 时，可视化以当前 textarea 内容 `parseJsonArraySafe` 渲染；解析失败显示降级提示，不阻断保存校验路径。

### 3.3 后端

**默认不改后端。** 若 GET 详情缺少 `description`/`status`，前端继续本地 state；远程 rules 拉取失败静默降级到 criteria 派生。

可选最小后端（仅当联调需要且不影响现有契约）：不在本波强制；优先前端派生。

### 3.4 样式

`apps/web/src/styles.css` **文件末尾**追加：

```css
/* === W4-C8b === */
```

前缀类名：`at-overview-*` / `at-param-table` / `at-kind-badge*`，避免与他 Worker 附录冲突。

## 4. 所有权与禁区

| 可写 | 禁止 |
|------|------|
| `ActionTypeEditorPage.tsx`(+test) | `LinkType*` / `Capability*` / `DocumentIntelligence*` |
| action 相关最小后端（本波尽量 0） | `nav` / `main.py` |
| `styles.css` 末尾 `W4-C8b` | push / 改 m1 / merge |

## 5. 验收

- Overview 可见 Input+Rules 双列；参数表与类型徽章可见
- 创建/保存/试跑路径不变；JSON 坏数据时可视化降级、保存仍走原校验
- vitest 覆盖新纯函数
- commit：`w2(C8b): ...`；交付 `W2_W4_DONE.md`

## 6. 风险与回滚

- 远程 action-rules 内存 store 无持久化 → 仅增强展示，失败不影响 CRUD
- criteria→kind 为启发式，非 Foundry 真规则引擎 → 文案标明「派生预览」
- 回滚：还原本页可视化块 + styles 附录 + DONE/方案即可

## 7. 建议下一批 226 页面

- `ontology-action` 全量视觉对账（Dependents、工具栏缩放、信息表 Tool desc）
