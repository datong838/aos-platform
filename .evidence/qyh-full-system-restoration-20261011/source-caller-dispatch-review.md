# 栖月汇原写者调用方分派核对

基线 m1 d5acab726、权威 AOS-001875，父 Task qyh-full-system-restoration-20261011 的证据目录租约唯一且 ACTIVE。候选一为完整 Source 写者调用方/权限兼容切换，已登记在 source-writer-impact-review 和连接组件计划；依赖固定连接组件已完成，当前真实 ACL 仍不可直接撤权。候选二为既有企业 OIDC 与独立发布身份接入，用户已授权恢复，但缺既有入口/独立账号配置证据，不能伪造发布者。先完成不依赖账号的候选一调用方核对。

本次实际 AST 扫描原产品代码：46 个相关文件、55 个 Store 构造位置、161 个 Store 方法，其中 70 个方法接收外部 conn。每个来源文件绑定 SHA256，并独立全部回读相符。此计数不是 55 个写者，也不是 70 个 Source 写操作；源码字面 SQL 和调用表达式仅用于定位，动态 SQL、助手方法及运行时授权仍须逐项复核。

原 AipProductionContractStore 同时服务普通合同/运行态、通用 Plan 以及签名 BI Plan。SignedBIPlanPreparationService 将 connect_factory 同时用于自身依赖读取与内部 Plan Store；运行适配器也传入 TransactionBoundConnectFactory。因此全局替换 _connect_factory 或默认构造会扩大发行账户权限，或者拆开原同事务依赖/Receipt/CAS，不可采用。原 create/revise/freeze 的 in_transaction 路径须保留调用方连接和边界。

原 AipResponsibilityAssignmentStore 的 create_successor 直接写 Plan head/revision，同一 Store 的接管/观测记录仍属于运行态；不能整个 Store 改用 Plan 账户。原 AipContentDraftStore.register 则同时写 artifact 与共享 Receipt，必须按完整原事务依赖授权 Content 身份，不能只允许 Receipt INSERT。所有读方法及 run/Host transaction-bound 调用须保持原来源只读路径。

下一实施文件级方案：在 aip_production_contract_store.py 分离通用 Plan 写入口与合同 Receipt 写入口，明确保留原调用方 transaction；在 aip_responsibility_assignment_store.py 仅给 create_successor 选择 Plan 身份；在 aip_content_draft_store.py 对 register 使用 Content 身份；真实启动入口须采用已验证的固定配置组件，不回落普通 runtime。实施前另建这些产品文件的 Task/Lease，补齐方法操作清单、完整依赖 SQL 与原同事务测试，不能在父 Task 的证据租约下直接修改产品文件。当前 8 个既有 runtime 伪造边界 xfail 必须以真实克隆库正向和负向关闭，再进入当前库权限迁移。

本轮只新增 audit_source_caller_dispatch.py、本核对与 source-caller-dispatch.json；没有数据库操作、服务切换、权限变更或外部效果。全系统、正式身份、八工作台和自然首链均未验收；原开发与历史数据保留。
