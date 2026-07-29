# W2_DONE — A2 模块接口 schema CRUD

> Worker：W2 · 分支 `feature/223-worker-2`  
> 完成时间：2026-07-29

## 改动摘要

将 `/workshop/module-interface` 从「派生只读展示」升级为 **入参/出参 schema 可增删改 + GET/PUT 持久化**，目标完整度 45%→65%。

## 文件列表

| 文件 | 动作 |
|------|------|
| `apps/web/src/pages/s2/ModuleInterfacePage.tsx` | **新建** 完整页面 + CRUD |
| `apps/web/src/pages/s2/ModuleInterfacePage.test.ts` | **新建** 纯函数单测 |
| `apps/web/src/pages/s2/extras.tsx` | 迁出页面，仅 re-export |
| `services/aos-api/aos_api/module_interfaces.py` | 规范化 name/key/direction；可选 outputParams 合并 |
| `services/aos-api/aos_api/routers/modules_interface.py` | InterfaceBody 增加 `outputParams` |
| `apps/web/src/styles.css` | 末尾 `/* === W2-A2 === */` 编辑表样式 |
| `W2_A2_方案.md` | 开工方案 |
| `W2_DONE.md` | 本交付说明 |

**未改**：`routes.tsx`（仍 `import("./extras")`）、Variables / Draft / Canvas / nav

## 验收要点

1. 选中模块后 `GET /v1/modules/:id/interface` 加载字段表  
2. 可 **+入参 / +出参**、改 name/type/direction、删除行  
3. **保存接口** → `PUT`，刷新后回显一致  
4. API 失败时展示「演示路径 · MOCK」并可本地继续编辑后重试保存  
5. 嵌套 Loop 示意、模块列表 / Runtime / 创建 Module 仍可用  

## 自测

| 项 | 结果 |
|----|------|
| `vitest` `ModuleInterfacePage.test.ts` | 8 passed |
| `pytest` `TestModuleInterface` | 3 passed |
| 后端 `normalize_entry_params` 冒烟 | ok |

## 风险 / 回滚

- 出参与入参同存 `entry_params`（带 `direction`），**无新表列**；旧 seed 无 direction 时默认 `input`  
- 回滚：revert 本 commit；`extras` re-export 可改回内联（不推荐）  
