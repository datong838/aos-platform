# W5CB4 E10：SourceSelection 产品准入的当前条件与候选准备计划（2026-09-28）

## 上位复习和当前事实

231/231-9 的 BG-00/01/02 要求安装、授权来源、管道、配置、审批从产品入口自然衔接，不能由开发者手工拼 exact ref；失败结果不能重发。产品方案要求一条真实商品×客群假设×场景首链，数据层负责有来源、有水位的事实，不让工作台直读商城库。E09 后当前命名卷 `a0v_109`：安装 approved、4 发布包，正式源0、管道0、运行绑定0，Host/worker 均关。已有 `POST /v1/pipelines/{id}/source-selection-approvals`、运行控制审批及原键回执；它们要求完整 exact draft 与独立 `aos_runtime` 身份。当前安全预览缺该运行身份，直接从画布提交或把 Web 超管连接冒充 runtime 都不合法。旧画布可保存图，但不等于正式 SourceSelection。

本波最小业务结果：让产品明确显示“当前缺什么、哪一步可安全继续”，并形成可审查的当前候选准备合同；不因空源或无 runtime 身份制造审批行/执行权。若审计证明无需新后端读口，复用现有接口并缩小改动。选择候选是只读，真正 POST 审批及新运行身份启用必须在证明完整现行图、映射、schema、遮蔽策略、签名制品、安装/配置/epoch 和权限后单独经过失败测试；本波不伪造这些引用。

## 文件级候选清单（编码前冻结）

- `services/aos-api/aos_api/data_os_store.py`：`e5adf8a3b44acc2a42ed906f0214d4fb1146915a1a88548fec36fcf2c7fb6c31`；增加单次 repeatable-read、tenant-scoped 的正式管道/来源修订/已保存图存在性读取，不输出连接密钥或完整图，不改已有写路径。回执存在才标识 E09 正式登记；只给候选状态，绝不签发执行资格。
- `services/aos-api/aos_api/routers/pipeline_controls.py`：`106550efaf777eec456b5d3efcd4c57877fc5a8ec6edad301365311b25195b54`；新增只读、principal/tenant-scoped readiness 口，输出缺失项与下一合法入口；本波不读取或试探运行身份密钥，前三项齐全仍统一报告需由原 Owner 精确复核，不能称可审批。不改变既有审批命令。
- `services/aos-api/aos_api/pipeline_control_service.py`：`185527da9985a83a073976b4f9bafca42cc272c0921bea6bbc8f533540ea841f`；必要时增加不触源、不分配执行权的 current candidate/preflight 服务，不能把存在性当签名/权限通过。
- `apps/web/src/pages/s2/pipelineCanvas.tsx`：`e39ce6f651538532ca5018a03f23166108a63ba0e2cb4ba6af8c7da510deb06b`；接入清晰的 SourceSelection 准入面板。优先新增隔离组件 `PipelineAdmissionPanel.tsx`，不改画布旧保存/预览路径；显示缺失项和正式下一步，只有完整权威候选才可显示审批动作。
- 新增 `services/aos-api/tests/test_pipeline_admission_readiness.py` 与 `apps/web/src/pages/s2/PipelineAdmissionPanel.test.tsx`；覆盖后端 HTTP/存储租户隔离、前端空态/失联、绝无自动审批；更新 `services/aos-api/tests/test_domain_router_manifest.py`（`aa09069ff63caf82c18b081943dc8fcef352b9ecf77d5082061f60925cff778e`）的精确封印。新增文件必须先在本计划补目录和合同再编码。

## 本波只读合同

`GET /v1/pipelines/{pipeline_id}/source-selection-readiness` 使用当前 principal 范围，在同一 repeatable-read 事务只读取原 `meta_pipeline`、`meta_source`、`phase5_pipeline_graph` 与 `pipeline_registration_receipt`；不连商城来源，不返回 props/密钥/图节点。公开结果仅含 pipeline ID、是否正式登记、已登记来源 ID、当前来源配置修订、已保存图修订，以及按固定顺序列出的 blockers/nextAction。没有正式登记即 `REGISTER_PIPELINE`，源缺失或修订漂移即 `REGISTER_SOURCE`，图缺失即 `SAVE_GRAPH`；即使前三项齐全，运行身份/安装/映射/schema/遮蔽策略尚未经原 Owner 同事务核验，状态仍是 `NEEDS_EXACT_RUNTIME_REVALIDATION`，绝不返回 `ready=true` 或可直接发送的 draft。前端只渲染此只读结果，不在本波启用审批按钮；失联显示“未核清”，而不是可用。

## 串行 9 步与退出门

1. 核实产品/技术合同、当前路由、画布、运行身份及反向调用者；2. 将真实候选的来源/配置/图/安装/角色 exact 输入与失败原因逐项冻结到本文件；3. 最小实现只读准入/面板；4. 专项负例；5. 邻接累计回归；6. 浏览器验收当前安全空态和已有权威路径；7. 方案/代码一致性与越权风险复审；8. 验收证据落盘；9. 精确提交并更新上下文/Prime，自动进入 E11 审批生产者或下一个经证据确认的核心切片。

若当前源/安装/图/凭证不齐，输出明确 BLOCKED 与下一合法配置步骤；不能为做绿而取历史卷、降权、复制旧代权限、启 Host/worker、手工 `run_definition`、读商城源或重发未知请求。每天以当日最新代码和原命名卷完整重启并核验，随后继续 Loop。
