# P6B 模型路由生命周期施工包

## 上位方案复习

- 依据 `22-AIP-7-exact模型路由Provider-Eval与运行就绪增量优化方案.md`，canonical `ModelRouteRevision` 是唯一运行路由 authority；旧 `/api/models/router/draft` 只保留兼容草稿维护，不得成为 AgentRun 真源。
- 路由候选必须引用 exact `RegisteredModelRevision`，并绑定 exact RuntimePolicy/Eval；Health、价格、Eval 或容量不满足时继续失败关闭。
- 回滚不覆盖历史 revision，也不直接恢复流量；只能从历史 revision 追加一个新的 `draft`，再重新走校验与审批链。

## 当前波文件级清单

1. `services/aos-api/aos_api/aip_model_runtime_store.py`
   - 增加租户内不可变路由历史读取。
   - 增加基于当前 head CAS 的回滚草稿追加；只生成 `draft`，不激活运行。
2. `services/aos-api/aos_api/routers/aip_model_runtime.py`
   - 暴露 canonical 路由历史与回滚草稿命令；scope 只来自 Principal，命令要求 Idempotency-Key。
3. `apps/web/src/api/aipModelRuntime/{contracts,parser,index}.ts`
   - 增加严格 `ModelRouteRevision` parser 与历史读取客户端。
4. `apps/web/src/pages/s2/aip.tsx`
   - 在模型路由页增加权威路由生命周期、exact 依赖、不可变历史和“从历史创建回滚草稿”。
   - 明确兼容草稿与运行 authority 分门；不提供绕过 Eval/Health 的激活按钮。
5. `apps/web/src/api/aipModelRuntime/parser.test.ts`、`apps/web/src/pages/s2/W3CModelRouterInteractions.test.tsx`、`services/aos-api/tests/aip/test_aip_model_runtime_api.py`
   - 覆盖 strict parser、租户隔离、历史顺序、CAS 冲突、只追加草稿、前端重读与失败关闭。

## 退出门

- 专项测试、TypeScript、生产构建、diff check GREEN。
- 内置浏览器连接可用时，以 `org-org/dev-project` 只读核验 canonical 路由历史与页面分门；不点击任何真实写命令。
- 无 Provider 调用、无模型试聊、无生产流量切换、无真实业务数据修改、无发布。
