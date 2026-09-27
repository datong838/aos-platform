# W5CB4 E12：当前 SourceSelection 候选读取与产品恢复入口计划（2026-09-28）

## 上位目标与本波限制

231/231-9 BG-00/01/02 和栖月汇产品方案要求安装、授权来源、管道、数字同事配置、审批从产品自然接线；真实数据更新以后才谈 Occurrence→Case/Run→建议→内容→复盘。E09 有正式管道登记回执，E10 仅给缺项，E11 有纯精确候选编译器，但还没有当前权威读取与产品生产者。当前 m1 `3f945711`、原卷 `a0v_109`：安装 1、来源/管道/绑定/Selection 均 0，Host/worker 0。当前无源，不能在主库造样本或读微商城源。旧 12 Run 冻结、230 L0 挂起。

本波先打通**只读当前候选解释**与恢复边界，不提前开放 POST 审批。调用 E11 编译器必须在同一租户当前安装/图/源/配置的可信快照和独立签名制品读取成立时；否则返回显式 blocker。不得从网页请求自报“当前”或“已签名”，不得把 Web 超管 DSN 复用为 runtime worker，不能以 E10 readiness、编译成功或旧导出目录作为授权。实际正式 Selection 的 POST、原键持久化/对账与运行身份启用分开经失败测试后开门。

现场审计补证：当前唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 的 revision 3 为 `approved`、`active_revision=NULL`；当前源/管道/绑定均 0。`CurrentRuntimeReleaseArtifacts` 从独立 runtime 连接读取签名制品，而本实例还没有该独立连接。故本波**只能实现同一应用只读事务的诊断生产者**，不能调用 E11 编译器生成可交付草案；日后具备独立运行身份和 active 安装时再按本文上门复审补接。把这些事实明确呈现为 `INSTALLATION_NOT_ACTIVE`、`RUNTIME_BINDING_MISSING` 等阻断是推进产品闭环，不是假装审批已就绪。

## 文件级清单与前哈希

- `services/aos-api/aos_api/data_os_store.py` (`b0f3175366d1a2bf61282555bfce848ec75bfeaedb530dd1c318acfed2d68167`)：复用 E10 只读 scoped snapshot，增加候选所需的正式登记、来源配置 exact ref、图 payload/hash/revision 的受限内部读取；不返回源 props/secretRef，不改写路径。若当前 app 角色无权限，明确阻断，不升权兜底。
- 新增 `services/aos-api/aos_api/pipeline_source_selection_candidate_reader.py`：组合当前安装/binding/config、原签名包导出资产与 E11 纯编译器；候选 0/多解/旧代/漂移/身份缺失统一 fail closed，公开投影仅 blocker/nextAction 和非敏感定位，不直接输出可 POST draft。可信事务/制品读取边界必须写清；如果无法在同一当前边界证明，缩小为诊断读取，不声称可审批。
- `services/aos-api/aos_api/routers/pipeline_controls.py` (`552c342c38113b0b49ba505e9f30239c4d039df3ce794d8766f847da1bc4ead8`)：新增 principal/tenant-scoped、`no-store` 候选诊断 GET；不新增审批 POST 或执行入口。
- `apps/web/src/pages/s2/PipelineAdmissionPanel.tsx` (`b2fc95254a8269f94285ade397cd524efd4b12a0796d72cf761e614a5c21c1a0`)：在 E10 面板显示安装/身份/签名缺项及原键恢复解释；不做自动重发。
- 新增后端候选读取/HTTP 负例测试、更新前端准入测试及路由 manifest；若需新增迁移/角色/额外表，停止先修订本计划，不悄悄扩权。现有 `RuntimeViewReader` (`de7c69823d5f7e70ae751ebb187efb913d5f7ef096d05fe5fc4c26f1986571f8`) 优先复用，不修改其有效控制语义。

## 9 步和退出条件

1. 复习上位合同、E09–11、当前身份/安装/图/签名 API 和反向调用者；2. 细化以上文件级清单与 exact 输入/输出、失败码；3. 最小只读实现；4. 专项租户/旧代/竞态/缺失/多候选负例；5. 邻接累计回归；6. 浏览器当前空态验收；7. 方案/代码/越权风险复审；8. verification 落盘；9. 精确提交、更新 AOS 上下文与独立 Prime，自动进入下一波原键审批产品生产者或被现场证据证明更靠近首链的切片。

任一当前权威不明、缺真实源/运行身份、旧代、未知提交结果均阻断。单次请求不得读取商城源、运行 Host/worker、手工 run_definition、补旧快照或重发。每天以当天最新 m1 与当前权威命名卷完整重启数据库/API/Web，验版本、端口、页面、核心功能，随后继续 Loop。
