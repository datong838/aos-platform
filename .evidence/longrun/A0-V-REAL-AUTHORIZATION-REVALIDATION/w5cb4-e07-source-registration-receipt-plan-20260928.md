# W5CB4 E07：数据源登记持久 Receipt 与未知结果对账计划（2026-09-28）

## 上位、实际阻断和界限

231 A1/231-9 BG-00/01/02 首链要求产品内可配置、幂等 Receipt、未知结果可恢复；不能靠开发者重发或读源库。E05 当前卷源配置 0；E06 移除了自动 `/test` 并让未知请求跨刷新冻结，但现有 `/v1/sources` 无正式登记 Receipt，同 ID 元数据无法证明原请求，用户仍无法安全解冻。SourceSelection Owner 已存在，但当前源、管道、RuntimeBinding 均 0，直接审批不可行。本波只修正式登记和对账契约，不输入/读取商城凭证、源表或商品行，不启用 Host/worker、SourceSelection、Provider 或旧 Run。

## 文件级清单与前哈希

- `services/aos-api/alembic/versions/a0v_108_source_registration_receipt.py`（新增）：在 `a0v_107` 后增加 tenant-scoped 不可变 `source_registration_receipt`，保存请求摘要/幂等键、源 ID、正式配置修订和公开元数据，不含连接密钥；RLS/ACL/不可变历史门。迁移仅增量，不删旧表/数据。
- `services/aos-api/aos_api/data_os_store.py`：`6c0a9d1e6e80959ddbca0c508eb67d0fa629beac47588c586a89b79e0dd015d6`。在原 `persist_source` 同一事务写源及 Receipt，key 重放只回原结果、不同请求冲突；提供 tenant-scoped 只读 Receipt 查询。保留无 key 旧调用兼容，绝不借 Receipt 绕过源配置版本检查。
- `services/aos-api/aos_api/routers/wave_ext.py`：`029908890a5a6b7fb34a3dda98ab437a798b12da776aca344228978dc1915456`。只在正式新产品调用带 key 时走 Receipt，增加 key 精确 GET；请求摘要由服务端固定计算，响应仍只投影公开元数据，不输出 secret。现有老客户端保留原兼容行为。
- `apps/web/src/pages/DataPage.tsx`：`8e38cf18b46b4193093e808e3e27b733332d54310df1623c48b80fb5bb67698c`。pending marker 增加随机 key（不含凭证）；未知时只读查原 key Receipt 并复核 sourceId、runtimeMode、configurationRevision，未受理证明不足仍冻结；同次成功也回读 Receipt。绝不把 GET 同 ID 当 Receipt。
- `apps/web/src/pages/DataPage.source.interaction.test.tsx`：`ba8ef4253297086f9fa34bd7bec5af9437f7a2b67160f16d66a3de1d43a0c0bf`；新后端专项测试文件（新增）；覆盖同 key 同 payload、冲突、跨租户、响应丢失后 GET 对账、无密钥泄露、绝无 `/test`/离线队列。
- `services/aos-api/tests/test_domain_router_manifest.py`：`cdc796fa284acef6c3df717567d7102f18421fd5cd0c18f4c5ec005332822f21`。新增唯一只读 Receipt 路由后更新精确路由数/摘要/OpenAPI 路径数，保留重复路由为 0 的检查。
- `scripts/a0v_current_preview_bootstrap.py`：`a85533f5b61c4756e5f04317c14a2a3b573cbea167c523806ea96579422d2f8d`；`scripts/a0v_current_preview_http.py`：`e97a2e08d911f9e32367a46cd770659808e5c861825687b4de34cd71ce3fb7e4`。只有当前库经独立备份、迁移与负例验证后才将精确预检头由 107 改为 108；若迁移不安全，两脚本和当前运行都维持 107，不用关闭校验来让新代码启动。

## 串行验收与停止条件

1. 先做模型/后端测试与迁移隔离验证，再接产品调用；构建、专项、邻接、累计回归，确认未新增源读或自动动作。
2. 当前命名卷升级前生成**新的当前时点**独立可校验备份，不删原卷、不去历史卷找业务行；核对目标容器/卷/DB/schema 和备份可恢复性。任何不明结果先冻结，不重跑迁移。
3. 仅当隔离验证及当前备份门都通过，停当前 8080/8434、在原卷对现有 DB 执行 `a0v_108` 非破坏性迁移；只读回读版本、RLS/Receipt 空态、原安装/方法/公开数据不变，再以最新代码+同卷完整重启。失败保留实例与备份，不私自覆盖/回滚数据。
4. 浏览器仅验收空态/安全文案，不填真实源凭证或 POST 真实配置；verification 落盘、精确提交、AOS/Prime 上下文更新，自动进入后续“正式源与 SourceSelection 产品准入”波。E07 不宣称商品首链完成。
