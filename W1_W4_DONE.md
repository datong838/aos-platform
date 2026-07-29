# W1_W4_DONE — C8a 链接类型详情可视化

## Commit

分支 `feature/223-worker-1` · 信息：`w1(C8a): link type relation SVG viz + join cards`  
（完整 hash 以 `git rev-parse HEAD` 为准，交付回复中给出。）

## 改了什么

| 文件 | 变更 |
|------|------|
| `W1_W4_C8a_方案.md` | 方案文档（先方案后代码） |
| `apps/web/src/pages/s2/LinkTypeEditorPage.tsx` | SVG 双节点关系图 + 基数/rel 标签；Join method 卡片；`normalizeLinkType` 缺字段降级；RID 信息行；CRUD 保留 |
| `apps/web/src/pages/s2/LinkTypeEditorPage.test.ts` | layout / normalize / truncate 单测（35 passed） |
| `apps/web/src/styles.css` | **仅末尾** `/* === W4-C8a === */` |
| `services/aos-api/aos_api/routers/ontology.py` | `_row_to_link` 派生 `joinMethod`/`symmetric`/`rid`/`status`（不改表） |
| `W1_W4_DONE.md` | 本交付说明 |

**未改**：Action*/Capability*/DocumentIntelligence*/nav.ts/main.py；未 push / 未改 m1 / 未 merge。

## 如何自测

```bash
export PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH"
cd apps/web && npm test -- src/pages/s2/LinkTypeEditorPage.test.ts
# → 35 passed

cd services/aos-api && PYTHONPATH=. python3 -c "from aos_api.routers.ontology import _row_to_link; print(_row_to_link({'id':'lt-x','name':'X','src_type':'A','dst_type':'B','rel':'r','cardinality':'ONE_TO_MANY','expected_edges':0,'mdo_approved':False,'published':True,'description':''})['rid'])"
```

## 验收对照（227 · C8a · 50%→70%）

- [x] 关系可视化：SVG 源/目标节点 + 边 + 基数徽章 + rel 副标 + 结构化摘要
- [x] Join method 卡片选择（四枚举契约不变）
- [x] CRUD / 规模红线 / 左右导航保留
- [x] API 缺 joinMethod 等字段时 `normalizeLinkType` 填默认；图渲染异常走文本降级
- [x] styles 仅末尾追加；所有权文件未越界

## 风险

1. `joinMethod`/`symmetric` 本波**不入库**，刷新后回派生默认（方案已声明；下一批可 ALTER）。  
2. Planner 合并 `styles.css` 末尾注意与 C8b/B5/E1 冲突。  
3. 视觉稿 Join 三选与系统四枚举不完全一致，本波不改契约。

## 建议下一批 226 页面

- `ontology-link.html`：Ontology/Status + ID/RID 信息卡像素对账  
- Join 卡片与视觉三选枚举对齐（若产品确认改契约）
