# AIP 模型管理五页面可操作性独立复验

- Task：`AIP-MODEL-MANAGEMENT-FIVE-PAGE-OPERABILITY-AUDIT-20260829`
- 时间：2026-08-29
- 租户：`org-org/dev-project`
- 浏览器：Codex 内置浏览器
- 代码基线：`m1@0f77641c`（功能实现提交 `46b2bffa` 已在历史中）

## 浏览器逐页结果

| 页面 | 实测控件 | 结果 |
|---|---|---|
| `/aip/model-catalog` | 目录浏览、搜索/筛选、平台设置、模型启用、已注册、模型对比 | 各视图真实切换；目录只展示当前租户 3 个 Agnes 模型；对比计数实时变化；无虚构组织、协议或模型家族 |
| `/aip/model-providers` | 配置、管理凭据、插件/适配器入口、详情 | 配置与凭据页面可进入；opaque `secretRef` 原值保存后 CAS 重读到 `v3`；未读取或回显凭据正文，未触发模型调用 |
| `/aip/model-router` | 规则编辑、保存、权重、熔断、回退链、路由测试、导出 | 路由草稿原值保存并重读到 `v4`；熔断草稿原值保存并重读到 `v4`；路由测试因当前 0/3 就绪保持禁用；未激活运行 |
| `/aip/capacity` | 今日/本周/本月、用量、速率限制、预留容量、项目限额管理/取消 | 页签和周期切换均改变真实视图；项目限额编辑器加载 RPM 60 / TPM 60000 并可取消；精确容量池可读，预留池诚实显示未开通 |
| `/aip/model-runtime` | 刷新权威快照、刷新模型运行状态 | 生成时间从 21:51:50 更新到 21:51:51，再到 21:51:52；0/3 路由与 Health 过期原因一致 |

## 回归

- Web 全量：`256 files / 2325 tests passed`。
- API 定向：`42 passed`。
- 当前五页面没有复现可点击但无状态变化的确定性死控件。
- 首次测试命令因非交互环境未包含 Node 路径而失败；补入项目既有 Node 20 路径后全量通过。该问题不属于产品代码缺陷。

## 安全边界

- 未调用真实 Provider。
- 未解析、读取或写入 Secret payload；只重写并精确重读既有 opaque 引用。
- 路由与熔断仅保存非运行草稿；未激活 canonical runtime route。
- 未切生产流量、未写真实业务数据、未执行迁移、未发布。

## 结论

`AIP_MODEL_MANAGEMENT_FIVE_PAGE_OPERABILITY_REVALIDATED_GREEN_NO_EXTERNAL_EFFECT`

本结论只证明五页面控制面可工作且运行门失败关闭，不把过期 Health 或 0/3 路由改写为 operational GREEN。
