# 228 Wave 3A W1：Pipeline Canvas 一致性修复方案

> 范围：Pipeline Canvas graph hydrate/save、Phase5 graph 持久化与专项测试
> 基线：`c33d8f6`
> 原则：最小改动、失败关闭、服务端真实持久化、请求与响应严格关联

## 一、问题与验收

1. **PC-08**：保存请求返回前继续编辑时，旧响应不得清除新编辑的 dirty 状态。
2. **PC-09**：`pipelineId` 变化时立即隔离旧 graph；旧 GET/PUT 响应不得污染新管道。
3. **PC-10**：保存成功必须同时确认 `pipeline_id`、`pipeline_type`、`write_mode`、nodes、edges 与请求快照一致。
4. graph 使用项目既有 PostgreSQL `connect()` + JSONB 事务模式持久化；`persisted=true` 仅在事务提交并返回一致快照后出现。
5. graph 读取、内存 hydrate、替换和返回均处于完整锁保护；数据库以单行完整 JSONB 保证跨进程原子快照。
6. 折叠属性栏后选中节点自动展开。

## 二、前端方案

- `editRevisionRef`：每次会改变保存内容的操作递增；保存捕获 request revision。响应返回时仅当当前管道和 revision 均未变化才清 dirty。
- `loadGenerationRef`：每次 `pipelineId` 变化递增；graph GET 只接受当前代次且 `pipeline_id` 匹配的响应。
- 切换管道时同步清空 graph、base node ids、位置、额外节点和边，并在新 graph hydrate 前禁用写交互。
- 保存请求构造不可变 snapshot；响应按稳定排序后的节点/边和稳定 JSON config 做严格比较。任何不一致进入失败反馈并保留 dirty。
- 保存期间允许继续编辑，但旧响应只确认其 snapshot；若出现后续编辑，显示“此前版本已保存，仍有未保存更改”。

## 三、后端方案

- 在 Data OS schema 增加 `phase5_pipeline_graph(pipeline_id, payload JSONB, revision, updated_at)`。
- replace 在数据库事务中对单行完整 payload 做 UPSERT，并返回数据库实际 payload；失败时不更新内存，也不返回 `persisted=true`。
- get 优先读取持久化 graph；命中后在全局锁内 hydrate 并生成完整一致快照。未持久化的既有 Phase5 单元仍读取内存。
- replace 的跨管道 ID 校验、持久化、内存替换、历史和响应快照均置于同一锁内；数据库单行事务负责跨进程可见性与原子性。
- 普通 `reset()` 只清内存，绝不删除共享开发库数据；仅测试 fixture 显式请求清理，并按该测试进程已知的 pipeline ID 定向删除。仅清内存模式用于模拟进程重启。

## 四、测试矩阵

- 前端：切管道旧 GET 忽略、保存中二次编辑、错误响应、请求失败保 dirty、保存后重载 hydrate、节点选择自动展开、KeyboardSensor 节点移动。
- 后端：DAG/悬空边不变、跨管道 ID 不变、数据库重启重载、并发 GET 不出现部分 graph、API 返回持久化真实快照。
- 回归：Pipeline Canvas 定向测试、Web 全量、Phase5 后端专项/全量相关、TypeScript。

## 五、风险与回滚

- PostgreSQL 不可用时保存失败关闭，不回落为内存“成功”。
- 单行 JSONB 上限由请求 nodes/edges 数量限制约束；本轮不引入新图拆表或迁移框架扩张。
- 回滚时删除本提交即可；新表为独立附加表，不覆盖现有 `meta_pipeline` 数据。
