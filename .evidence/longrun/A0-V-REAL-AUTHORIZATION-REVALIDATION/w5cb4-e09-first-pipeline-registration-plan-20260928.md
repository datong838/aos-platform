# W5CB4 E09：首条管道正式登记与产品入口计划（2026-09-28）

## 上位复习和现状

231/231-9 要求安装/选授权数据/管道/SourceSelection 从产品入口形成自然链，未知结果不可重发。当前 `a0v_108` 命名卷安装 approved、源 0、管道 0、绑定 0；浏览器“管道构建”0 管道，“新建管道提案”必须先选既有管道，不能产生首条。旧 `POST /v1/pipelines` 在 `wave_ext` 先改内存再调用 `_persist_safe`，失败可能被吞，并分别保存管道/数据集，无持久幂等回执。因此它不能承担首条正式管道的可恢复产品生产者。本波不改旧客户端行为，新增基于同一 Data OS Owner/表的窄正式登记入口，不增加第二真源；登记仅配置，不执行/读商城源。

## 文件级清单（修改前 SHA-256）

- `services/aos-api/alembic/versions/a0v_109_pipeline_registration_receipt.py`（新增）：增量建 tenant-scoped、不可变、RLS 的管道登记回执，原 key/request hash/源配置修订/管道与数据集 ID/公开结果，FK 指向原 Data OS 行；不删旧表/卷。
- `services/aos-api/aos_api/data_os_store.py`：`0af745f9be5a308640e7d9452cdfd632381cdbaac6585bb06707255ff3baa9f5`。新增正式 `register_pipeline`：当前源与配置修订存在、管道与数据集 ID 未占用、原 key CAS，同一事务写管道/数据集/Receipt；同 key 同请求只回原结果，冲突 fail closed；GET 原 key 只读回执。旧 `persist_pipeline` 保留兼容，不在新路径使用 `_persist_safe`。
- `services/aos-api/aos_api/routers/wave_ext.py`：`b1ceb894e44a775434106da6c9f9637ed7a09c595dbbabd726a0d30266925a28`。新增严格 POST `/v1/pipeline-registrations` 与 GET 原 key 回执，当前 principal tenant-scoped，不调用执行/测试源；提交后才更新现有可见列表缓存，未知不写入“成功”状态。
- `apps/web/src/pages/s2/data.tsx`：`bdde3959d6bcd16c9f2913afb2fb4690ba70459ed0e78857ba024dc2caee2e69`；新增 `apps/web/src/pages/s2/PipelineRegistrationPanel.tsx`。在管道页提供隔离的“新建管道”表单，必须选择当前可见源、输入规范 ID/名称；本地仅存非敏感 pending key/原请求摘要，失败/超时仅 GET 原 Receipt，对不上继续冻结，不重发；无源时导航到数据源管理，不创建样例管道。认证或租户改变时重置当前表单作用域。
- 新增 `services/aos-api/tests/test_pipeline_registration_receipt.py` 与 `apps/web/src/pages/s2/PipelineRegistrationPanel.test.tsx` 的 PG/HTTP、前端交互专项测试，覆盖同 key/不同 payload、跨租户、源配置变化、同 ID 不同 key、双行+Receipt 原子性、丢响应冻结/只读对账、绝无自动 execute/test；更新 `services/aos-api/tests/test_domain_router_manifest.py`（`2cbc6deba4d1758f715544db02b63e7300591b8cf31faf71b291db499204b63a`）的精确路由封印。
- `scripts/a0v_current_preview_bootstrap.py`：`e6dac08dfaec8c9aa73f3dffa88823c9125593f70223288e5c60f2d57dc93971`；`scripts/a0v_current_preview_http.py`：`6354c01e2a41aae07eddeb4f48be4c27e3a7d25f829223acd4da0d87e241ca76`。只有隔离升级、当前时点新备份及原卷安全迁移验证后把精确 schema head 108→109；不放宽 approved/绑定 0 检查。

## 串行 9 步与停止条件

1. 复习产品/技术方案与当前 Owner、路由、调用者；2. 本文件冻结最小接口与哈希；3. 增量实现，不改旧成功路径；4. 后端/前端专项；5. 邻接累计回归与静态构建；6. 独立 PG 用合成 file 源测原子性，当前卷迁移前独立可恢复备份；7. 新代码+同命名卷重启后浏览器验收无源空态/无自动效果；8. 方案/代码一致性、风险和 verification；9. 精确提交、上下文/Prime 同步，自动进入 E10 正式运行配置与 SourceSelection 产品准入。

若库/源当前性、Receipt 提交边界、备份或迁移结果未知，冻结原 key 和当前实例，不能手工重发/覆盖/清理旧行。E09 不读取商城源库、不启 Host/worker/旧 12 Run，不拿合成源算真实经营数据；没有真实授权源时验收只到产品安全空态。
