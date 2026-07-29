# W1_W3_DONE — C1 Wiki 详情 + C5 Wiki 差异

## Commit

分支 `feature/223-worker-1` · 信息：`w1(C1C5): wiki detail save + version diff with demo fallback`  
（完整 hash 以 `git rev-parse HEAD` 为准，交付回复中给出。）

## 改了什么

| 文件 | 变更 |
|------|------|
| `W3_C1C5_方案.md` | 方案文档（先方案后代码） |
| `apps/web/src/pages/s2/WikiDetailPage.tsx` | 接 `/v1/ontology/wikis`；主内容可编辑保存；版本列表；演示路径降级 |
| `apps/web/src/pages/s2/WikiDetailPage.test.ts` | API 映射 / 本地保存单测 |
| `apps/web/src/pages/s2/WikiDiffPage.tsx` | 版本 API + 本地 computeDiff；弱网演示路径仍可用 |
| `apps/web/src/pages/s2/WikiDiffPage.test.ts` | 映射 / resolveDiffTexts / 本地 diff 单测 |
| `apps/web/src/styles.css` | **仅末尾** `/* === W3-C1C5 === */` |
| `services/aos-api/aos_api/ontology_wiki_engine.py` | diff 附带 `from_content`/`to_content` |
| `services/aos-api/aos_api/demo/seed_phase4_ontology_wikis.py` | 固定 id `wiki-covid-homepage` |
| `services/aos-api/tests/test_phase4_ontology_wikis.py` | 固定 id + diff 全文断言 |
| `W1_W3_DONE.md` | 本交付说明 |

**未改**：ObjectType*/Property*/Function*/pipeline*/source*/nav.ts/main.py。

## 如何自测

```bash
export PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH"
cd apps/web && npm test -- src/pages/s2/WikiDetailPage.test.ts src/pages/s2/WikiDiffPage.test.ts
# → 54 passed

cd services/aos-api && python3 -m pytest tests/test_phase4_ontology_wikis.py -q
# 无 PG 时可用 importlib 冒烟 ontology_wiki_engine（已验证）
```

## 验收对照（227 · C1+C5）

- [x] C1 主内容可编辑并保存（PUT `/v1/ontology/wikis/{id}`；失败本地升版本）
- [x] C1 版本列表可见（GET versions；失败 MOCK）
- [x] C1 失败标「演示路径」+ 本地降级
- [x] C5 两版本文本 diff 可展示（本地 LCS）
- [x] C5 优先真 API 版本内容；弱则 MOCK 文本对比仍可用
- [x] 不碰禁止文件；styles 仅末尾追加

## 风险

1. 新建 Wiki 无 POST API，仅演示路径本地创建。  
2. 恢复到指定版本无后端 restore，前端仅本地提示。  
3. Planner 合并 `styles.css` 末尾注意冲突。
