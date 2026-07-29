# W1 · C8a 链接类型详情可视化方案（W4）

> 版本：v1.0（2026-07-29）  
> 目标：`/ontology/link-types/:linkId` **50% → 70%**  
> 约束：最小改动；严格所有权；不碰 Action*/Capability*/DocumentIntelligence*/nav.ts/main.py；禁止 push/m1/merge

## 1. 范围

| 项 | 做法 |
|----|------|
| 关系可视化 | 替换 Configuration 区简易箭头行 → **SVG 双节点 + 边 + 基数标签**；旁挂结构化摘要；失败降级为文本路径 |
| Join method | select → **卡片选择器**（保留现有 4 种枚举，布局靠视觉稿） |
| CRUD | **保持**现有 create/save/delete / 规模红线 / 左右导航 |
| 后端 | 已有 `GET/POST/PUT/DELETE /v1/ontology/link-types`；`_row_to_link` **派生** `rid`/`status`/`joinMethod`/`symmetric` 默认值，**不改表结构** |
| 前端 | 仅 `LinkTypeEditorPage.tsx`(+test) |
| CSS | `styles.css` **仅末尾**追加 `/* === W4-C8a === */` |

## 2. 可视化契约

### 2.1 纯函数 `buildLinkRelationLayout(form)`

| 输出 | 说明 |
|------|------|
| `width`/`height` | 固定 viewBox（约 420×120） |
| `src`/`dst` | 节点中心坐标 + 截断后的 label |
| `edge` | 线端点；`cardLabel` = `1:1`/`1:N`/…；`relLabel` = rel |
| `summary` | `{ src, dst, card, join, symmetric }` 供结构化降级 |

空 `srcType`/`dstType` 时仍出图，label 用 `—`。

### 2.2 渲染

1. SVG：左源节点 / 右目标节点 / 中线 + 箭头 / 边中基数徽章 + rel 副标  
2. 结构化行：`src → dst · 基数 · join`（SVG 异常或无类型时仍可见）  
3. 互换按钮保留，写回 `swapDirection`

### 2.3 Join 卡片

映射现有 `JOIN_METHODS` 为可点卡片；选中态边框高亮；描述文案保留。

## 3. 数据与降级

| 场景 | 行为 |
|------|------|
| GET 成功但缺 joinMethod/symmetric | `normalizeLinkType` 填默认（foreign_key / false） |
| GET 失败 | 已有 `err`；表单可继续编辑；图用本地 form（可降级） |
| 后端无 join 列 | 派生默认返回；前端本地态仍可编辑展示（本波不持久化 join/symmetric） |

## 4. 验收（对照 227 · C8a）

- [x] Overview Configuration 区有非纯文本的关系图（SVG 节点/边 + 基数标签）
- [x] Join method 为卡片式选择，CRUD 保存/删除不回归
- [x] API 缺字段或失败时可降级展示
- [x] 单测覆盖 layout / normalize；commit `w1(C8a): ...`；`W1_W4_DONE.md`
- [x] 不碰禁止文件；styles 仅末尾追加

## 5. 风险

1. `joinMethod`/`symmetric` 本波不入库，刷新后回默认（已有缺口；下一批可 ALTER）  
2. Planner 合并 `styles.css` 末尾注意与 C8b/B5/E1 冲突  
3. 视觉稿三选 Join（FK/Dataset/OT）与系统四枚举不完全一致，本波不改枚举契约

## 6. 回滚

还原 `LinkTypeEditorPage*`、`ontology.py` 的 `_row_to_link` 派生字段、styles 附录与本方案/DONE 即可。

## 7. 建议下一批 226 页面

- `ontology-link.html` 双栏信息卡（Ontology/Status + ID/RID）像素对账  
- Join 三选卡片与视觉枚举对齐（若产品确认改契约）
