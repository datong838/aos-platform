# SC4-5l6l growth 1.9 ProductEvent 候选验证

日期：2026-09-16  
方案：`sc4-5l6l-product-event-signed-successor-plan.md`  
基线提交：`31c1b0a2`

## 结果

新增不可变候选 `bundles/candidates/ecommerce/solution.ecommerce.growth/1.9.0`，首次冻结 tree hash 为 `sha256:c0998de7017d74f366a327dc60f9b9a18357a1fb14327ed8b35191cb59259d36`；资格前纠正后的最终 hash 见下方。冻结源 1.8 树仍为 `sha256:718548ad92a3715891b4b84060f0a2f22ad4baf6e492195573738e49c40ac8c4`。

1.8 的 90 个文件无删除。相对 1.8，只新增六个已评审领域模块与两个 ProductEvent 导出合同；只修改 `bundle.yaml`、注册入口、应用组合和八个自身版本引用。没有改变七工作台静态导航/UI、经营参谋前端、知识、Profile、策略或其他业务内容。

Manifest 与运行注册均为 25 项：14 项导航/UI、原九项增长 API、固定 `ecommerce_growth_event_control` 和 `analyst_workspace_view_v1`。SDK 纯运行验证可以从候选包导入 ProductEvent schedule/control/application，并通过安装包入口确定性构造 `runtime.analysis.start` 命令；输入保持不变。候选仍不包含 Host 数据库、租户身份或执行授权。

## 验证

- 新候选与 ProductEvent/分析合同定向回归：`72 passed`。
- 覆盖目标不可覆盖、1.8 基线漂移、作者注册漂移、领域源漂移、精确文件差异、Manifest/运行注册一致、25 项唯一贡献、SDK 纯运行与既有领域合同。
- Python 编译通过，`git diff --check` 通过。
- 服务恢复核验：8434、5173、18181、18432、18434、18435 均可连接；API 与 Runtime Host 进程存活。
- AR2 阶段验证器扫描 1956 个 Python 模块，`unclassifiedForwardDependencies=[]`、`unclassifiedReverseCallers=[]`、`bundleCrossLayerImports=[]`。它仍报告清册中既有模块及动态引用 hash 漂移；本步没有改动这些文件，因此保留为已知未清历史项，不宣称阶段验证器全绿。

测试退出阶段出现既有 JDBC 缓存日志流关闭告警，缓存计数为 0/0，不影响测试退出码与候选结果。

## 边界与下一步

本结果只冻结 1.9 候选，没有构建镜像、签名、发布、安装、分派或主库写。下一步进入新波第 1/6：先实现并在隔离 PostgreSQL 验证 receipt-first 的固定第十项分派扩展/收缩协议；该协议通过后才构建签名包并执行 E→F 切换。


## 2026-09-16 资格前纠正

签名资格实现前发现 1.8 基线不含 `product-event-save.contract.v1.json` 与 `product-event-control.contract.v1.json`。两合同是前序资格方案要求的包内签名资产，遗漏会让正确的 Host 资格检查拒绝候选。主库、Registry 和签名根尚未使用该候选，因此在发布前补入固定源 hash 并重跑全部候选测试；最终 tree hash 为 `sha256:6c27c24ae96bc2cb013526e2f431d3ee2d2fdb6925e0b3729f6a6e12c3c4472f`。
