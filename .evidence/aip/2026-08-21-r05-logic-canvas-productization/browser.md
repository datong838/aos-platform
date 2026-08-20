# R05 Logic 画布浏览器验收

- 浏览器：Codex 内置浏览器；前端 `http://localhost:5174`。
- 租户：`org-org/dev-project`（栖月汇商贸有限公司 / 默认工作区）。
- 入口 `/aip/logic` 自动选择第一个 exact persisted Graph，并替换为 `/aip/logic/ecommerce.logic.V01`；没有自动生成未保存模板。
- 编辑、运行历史、自动化三 Tab 与 URL 一致；任一时刻只有一个 `tabpanel`。
- `End` 从编辑切到自动化，`ArrowLeft` 从自动化切到运行历史；焦点和选中态一致。
- 运行历史显示 1 条服务端不可变记录，`production_written=false`；未触发试跑。
- 自动化显示 `ecommerce.logic.V01@1`、exact hash，并把 Uses 表示为“未接入/未观测”，没有把未知显示为 0。
- “新建 Logic 草稿”入口存在，但验收未点击；保存、安全试跑、发布及真实数据库写入均未触发。
- 深色主题初验发现历史左栏使用未定义 `--aos-surface-muted` 后退为白色；改为现有 `--aos-surface-hover` 后复验通过，无白底断层。

结论：R05 浏览器门 GREEN；功能、权威数据语义、键盘语义与 AOS 主题一致。
