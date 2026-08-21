# R01 · Provider Canonical Detail EvidencePack

- 波次：`R01 / UX25-01`
- 分支：`w1-aip`
- 开工基线：`d1a66dae9470a1cfe7509cdd32c22571b4c2d3f2`
- 正向租户：`org-org/dev-project`
- 负向 canary：`dev-org/dev-project`
- 数据与副作用：`NO_MIGRATION / NO_PROVIDER_CALL / NO_SECRET_PAYLOAD_READ / NO_REAL_DB_WRITE`

## 交付结论

1. `/aip/model-providers/:providerId` 已改为 canonical model-runtime authority 的只读详情页。
2. 菜单中的插件 ID 会通过 exact `dependencyRefs` 解析到当前 ProviderInstance revision；无实例的插件诚实失败关闭。
3. overview 只返回当前 Provider exact revision 对应的最新 Health，保留原始时效，不在读取时刷新或重解释。
4. 浏览器可达路径已移除明文 API Key/password 输入；前端 parser 拒绝 credential-shaped payload，只展示 opaque Secret backend 与 version。
5. 旧详情组件保留为 `LegacyProviderDetailPage`，但默认路由不可达，便于回滚而不重新暴露明文入口。

## 专项与累计验证

| 验证 | 结果 |
|---|---|
| Web targeted Vitest | `4 files / 21 tests passed` |
| API/store targeted Pytest | `13 passed / 1 deselected` |
| Vite production build | `GREEN` |
| Web cumulative | `195 files passed / 1971 tests passed / 1 unrelated baseline failure` |
| TypeScript cumulative | R01 文件无新增错误；2 个既有非 R01 错误保留为 baseline warning |
| `git diff --check` | `GREEN` |

被排除的后端用例 `approved_provider_plugin_exact_readback_is_principal_scoped` 固定断言旧插件 revision 2，而当前批准 revision 已为 3；该漂移不由 R01 修改。Web 全量唯一失败为 `CanonicalCapabilityPage.test.tsx` 的既有文案空格断言差异，R01 专项均通过。

## 浏览器验收

使用隔离端口启动当前 `w1-aip` 构建和 API，并以 `org-org/dev-project` 验收：

- `agnes-text`：解析到 `agnes-text-qyh-dev@7`；展示 endpoint、region、Secret backend/version、Health、模型、容量池和路由阻断原因；DOM 无 password 输入或 Secret payload。
- `agnes-image`：解析到 `agnes-image-qyh-dev@2`；同样不暴露 Secret payload。
- `vllm`：插件存在但无 ProviderInstance，页面明确显示不可发布的只读失败关闭态，没有伪造 Provider。
- `/aip/model-runtime`：展示 3 个当前 Provider、3 个当前 Health；Health 已过期时保持 0/3 ready，不伪造可运行。

运行事实显示当前 Provider 的 region 为 `China (Domestic)`，与历史审批中的 Singapore 口径不一致；R01 只读如实展示，不在无新审批时改写 authority。该差异转入 R04/R33 的运行权威对账。

## 回滚

回滚只需把 Provider 详情路由切回保留的旧组件；不得重新开放明文密钥输入。后端本波未迁移、未删除旧表或旧 Router，因此无需数据回滚。
