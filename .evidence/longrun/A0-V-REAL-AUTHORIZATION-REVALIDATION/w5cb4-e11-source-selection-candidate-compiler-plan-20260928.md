# W5CB4 E11：SourceSelection 精确候选编译器（2026-09-28）

## 上位合同与现场

231 的 A1 首链、231-9 的 BG-00/01/02，以及栖月汇产品方案要求用户从产品入口完成安装、授权来源、管道、配置和审批，不靠开发者手工接线。E09 完成正式管道登记及原键回执；E10 只读准入显示缺项，未授予审批。当前 m1 `a2e94e7b`、当前命名卷 schema `a0v_109`：安装 approved、4 包，正式来源 0、管道 0、运行绑定 0，Host/worker 关闭。旧 Host 引导脚本硬编码 `aos_meta_head`，不能用于当前卷。旧 12 Run 冻结、230 L0 挂起、不读取商城源、不手工 run_definition、不 push。

现有 `PipelineSourceSelectionOwner.append` 已在原事务中复验安装、签名制品、配置、图、源和窗口；不得用前端存在性、E10 readiness 或编译成功代替它。E11 先实现**纯、确定性、无数据库/网络/执行副作用的精确候选编译内核**，把多候选和漂移安全失败固定下来。当前卷没有授权源，不能进行真实审批。本波不配置新数据库身份、不启 Host、不写 Selection 行；E12 才在身份和当前数据齐备时接产品 API/原键恢复。

## 文件级清单与前哈希

- 新增 `services/aos-api/aos_api/pipeline_source_selection_candidate.py`：只接受经调用方读取的不可变当前引用/已核验制品资产描述/图，生成一个 `PipelineSourceSelectionDraft`；遇到 0 个或多个匹配组合返回明确 blocker，不降级猜选。纯函数不得访问文件、DB 或源库，不暴露密钥。
- 新增 `services/aos-api/tests/test_pipeline_source_selection_candidate.py`：精确单候选、零候选、多候选、图漂移、来源漂移、窗口、租户/安装/epoch 不一致和未核验输入的负例。
- 复用不修改 `pipeline_source_selection_owner.py` (`f344a95e6da2b02e9a3e252acb9326a1b4f4f0af7fa92fcd236380b8cc9d3771`)、`pipeline_runtime_control_contracts.py` (`5111af6469b09b5eaba9855fee94b1d219d695e0c35ff6ad0b2c0c8892ab5690`)、`routers/pipeline_controls.py` (`552c342c38113b0b49ba505e9f30239c4d039df3ce794d8766f847da1bc4ead8`)。若发现编译器无法在不削弱 Owner 的前提下复用，先修订本方案，不先改 Owner。
- 浏览器验收只检查当前安全空态 `/data/pipelines` 和画布准入；不通过页面发审批命令。

## 纯编译合同

输入必须由可信调用方分别提供：当前租户、正式登记的管道与来源修订、当前保存图及 hash/revision、同租户当前安装/代次/epoch/配置 ref、已发布且校验过的唯一包及其导出资产元数据、受限时间窗与读取预算。资产候选的 mapping/schema/masking 必须是原包导出的 exact path、版本和 SHA-256；不能从请求体自报“已验证”。对每个候选，复用 `derive_mapping_read_spec` 与 `verify_graph_read_spec` 比对固定 snapshot 图；仅唯一匹配才产生 `state=prepared/readOnly=true` 的草案。编译器自身无审批资格，返回草案后仍需 Owner 原事务全面复验；任何输入不明或多解均拒绝。

候选元数据与解析后的文档可能含字段说明，不能作为 HTTP 响应直接公开；E12 另定义最小公开投影。所有真实来源与 secretRef 不进入该纯函数的日志或证据。实现如需读已签名资产，应由调用方用原 `CurrentRuntimeReleaseArtifacts` 严格加载并验证，编译器只消费已验证值。

## 串行 9 步与退出门

1. 复习上位产品/技术合同、Owner、资产、反向调用者和当前 DB/服务身份；2. 冻结本文件级最小清单及失败合同；3. 编码纯编译器，不改既有 Owner/执行路径；4. 专项正反例；5. Owner、E09/E10、安装/配置邻接累计回归；6. 浏览器验收当前产品空态与控制边界；7. 方案/代码一致性和越权风险复审；8. verification 落盘；9. 精确提交、更新 AOS 上下文与 Prime 记忆，自动进入 E12 当前身份与只读产品候选接线。

停止条件：若无法证明资产元数据已经由可信调用方验证，或不能唯一比对图，则不生成草案；未知审批结果只查原键回执，不重发。浏览器/测试绿不代表真实首链、业务数据或配置已就绪。每天使用当天最新 m1 与原命名卷完整重启 DB/API/Web 并核验，随后继续 Loop。
