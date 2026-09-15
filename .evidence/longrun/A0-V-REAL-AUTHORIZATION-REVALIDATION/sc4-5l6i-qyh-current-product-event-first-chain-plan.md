# SC4-5l6i 栖月汇当前包真实 ProductEvent 首链方案

日期：2026-09-15
代码基线：`ed22f062`
任务权威：`A0V-QYH-CURRENT-PRODUCT-EVENT-FIRST-CHAIN-20260915`、`A0V-STANDALONE-RUNTIME-BUSINESS-WORKERS-20260915` 与 `A0V-CURRENT-ECOMMERCE-HOST-CUTOVER-20260915`，owner=`m1`，有效至 2026-09-17 23:59 +08:00。

## 目标与当前事实

本波把最终安装 C 从“包与容器可运行”推进到“真实数据变化能自然进入经营分析”。当前 C `044c2743-9700-4e84-a6c1-98670c94f005@5`、generation `09d2a19a-d85a-4c81-981c-87c1600944ea` 已 ready/enabled/unfenced，签名组合为 core 1.3、Niushop 1.22、growth 1.8、operations-base 1.2。

2026-09-15 通过受控 API 的正式 Source probe 重验 `niushop-qyh`：当前配置 revision `a84b6c79-8654-48f0-98c2-57d41b067b3d` 经 SSH/JDBC 只读连接在 2364ms 内返回 302 张表、未截断，包含 `ns_goods/ns_goods_sku/ns_order/ns_goods_evaluate/ns_pay/ns_express_delivery_package` 等；没有读取业务行或写上游。

主库的两个 SourceSelection/RuntimeControl 均绑定已退役历史安装，当前 C 为零；ProductEvent policy、Case、Run 均为零。既有 P02 真实首读证明 65 商品、39 active/18 inactive/8 deleted，但该证据是 2026-09-13 历史批次，不能替代本次新鲜读取。

另一个实现缺口是：`main.py` 的内嵌 Host 模式会随 Host 启动 ProductEvent Worker 与 AnalysisDataRequirement Worker，而 `a0v_ecommerce_runtime_host.py` 独立 Host 启动器只运行生命周期 Host。当前 API 为避免双写明确禁用内嵌 Host，因此若不修复独立启动器，真实事件不会自然消费。

2026-09-15 代码接线完成后复核运行所有权又发现：当前 C 的三个 OCI 资源由仍在运行的旧代码 Host 进程持有；Host 的正常退出会按合同释放其资源，而新进程不会凭数据库中已成功的旧 apply 回执冒充原 owner 重新接管。因而禁止直接停旧 Host 后继续把 C 当作 ready。安全路径固定为：先让控制器支持后继 D；再优雅停止旧 Host并读回 C 的实际释放状态；启动已含两个业务 Worker 的新 Host；通过正式 disable Receipt 把 C 收敛为 disabled/fenced/unknown 且资源 confirmed released；以 C 的当前 exact head 创建 D；由新 Host消费 D 的 prepare/verify/configure/enable，最终 D 成为 active/ready/enabled/unfenced并持有三个新资源。C 在 D 生效前不得卸载，且后续真实 P02 和 ProductEvent 引用全部绑定 D。

切换前快照于 2026-09-15 17:26 +08:00 冻结，旧 Host 随后优雅退出。实际读回 C 为 active@5、binding rev5/epoch4、enabled=false、fenced=true、desired=enabled、observed=unknown，三个资源均 released/observedRelease=true，原四项 operation均 terminal，canary=0。这是 Host cleanup 的正式未归属恢复态，不能再调用只接受 enabled/unfenced 的普通 disable。控制器新增窄化的 `settle-c`：先逐字段确认上述当前安装、配置存在、资源已释放且无未决 operation，再使用原 RuntimeDisableService 发出唯一 disable Receipt，由新 Host消费并把 desired收敛为 disabled；只有该 operation成功且再次读回满足 replacement predecessor合同后才能 create D。

2026-09-15 18:36 +08:00，D 的第一次真实 P02 批次 `scr-f22003e66e544ebe` 已知失败并停止。一次源调用成功读取 65 条，原始规范命令已不可变保存；没有 derived、Dataset Receipt、projection 或 canary 写。精确离线对账确认 64 条与权威对象一致，`niushop:1:32` 的 `stock/saleNum` 已变化而源 `modify_time` 未变化。旧批次键只绑定最大源游标，因此还与历史不同载荷 Receipt 撞键，权威层以 `IDEMPOTENCY_CONFLICT` 正确拒绝。该 Run 不满足“相同原命令可重放”的恢复条件，永久保留 failed；不得通过放宽同版本冲突、改旧 Receipt、改 Journal 或伪造源时间恢复。

修复采用已有正式 `aos.snapshot-materialization/v3`，不新增第二套版本算法：Niushop 后继包把 P02 从宣称可靠源修改时间的 v2 改为完整观测版本 v3，`time_basis=observation`，并在属性中明确 `sourceUpdatedAtBasis=observation`、`sourceModificationTimeKnown=false`。完整观测每次可形成新的诚实版本，源表内业务时间仍不得冒充修改水位。新批次幂等键自然随观测版本变化；内核的相同版本差异拒绝规则不变。由于签名包不可变，修复必须形成 Niushop 1.23 候选、签名并通过 D→E 正式重装后才能新读，禁止就地改 D 的签名资产或数据库 graph。

## Rules、主路径与停止条件

1. 先修独立 Host 生命周期接线，再配置真实链。ProductEvent Worker 与 DataRequirement Worker使用同一个 control plane、LivePreparedJobDirectory、stop event 和 Host health；Host 停止后两者必须退出。保持 API 内嵌 Host disabled，保持 QYH Cron disabled。
1.1. Host 代码切换必须走 C→D 代次迁移；不得把已释放的 C 资源写成 ready，不得通过手工容器或数据库修补绕过 Runtime Operation/Receipt。
2. 当前 P02 配置必须从切换完成后的 D 当前 installation/generation/config ref 与签名 Niushop 1.22 资产生成；复用正式 SourceSelection、RuntimeControl、ScheduleBinding Owner。不得复制历史 selection/control ref，不直接写控制表。
3. 当前源读取固定 `ns_goods/site_id=1`、SNAPSHOT、最多1000行、30秒、一次 source call；读前重验精确 source configuration 和 mapping/schema/masking hash。结果未知时按原 run/key/claim/journal 对账，不换键重读。
4. 真实批次必须保留 active/inactive/deleted 与原源时间语义，不把旧65条或前次窗口冒充当前数据。当前批次完成后由原 Journal、Dataset Receipt、SourceClaim 与 projection evidence交叉核验。
5. ProductEvent policy 必须引用当前 D 的 P02 SourceSelection、当前 Case/Profile/方法及现有正式 Approval；Event Control 只允许当前 D 的 extension dispatch。不得用 fixture、直接 SQL 或脚本自报 approval 生成可执行绑定。
6. “计划为空”先形成全店基线/商品尖刀验证 Case候选及有来源的经营问题；本波允许用正式 Case/Plan/Approval入口完成一次租户初始化配置，但事件后的 Occurrence、Analysis Run、Task/Run、DataRequirement 与后续恢复必须由 Worker自然产生，禁止逐表手工制造成功状态。
7. 若当前有效独立审批、职责、方法、预算、模型健康或十二源策略不足，保留准确阻断与已完成的真实数据证据；不扩大角色、不伪造批准、不用旧 Receipt 代替当前授权。
8. 正租户固定 `org-org/dev-project`；canary `dev-org/dev-project` 只检查零写。上游只读，无外部发布、触达、投流、价格或履约写；不 push，230 L0 挂起。
9. 相同阶段失败两次、来源结果未知、Host/数据库单写冲突、租户或 exact ref 漂移时停止该写动作，先读回原 Receipt；不重发未知操作。
10. 已知 `IDEMPOTENCY_CONFLICT` 的原 Run 保持 failed，不走 saved recovery；只有 1.23/D→E 完成并重新取得当前 SourceSelection/RuntimeControl/ScheduleBinding 后，才允许一个新 Run 做一次新鲜源读。

## 方案与代码范围

### A. 独立 Host 的业务 Worker 生命周期

- 修改 `scripts/a0v_ecommerce_runtime_host.py`：`_build_host` 返回 host 与其原 control plane，`_serve` 启动 lifecycle Host task，再从同一 control plane 构造 ProductEvent Worker 与 AnalysisDataRequirement Worker。两个 Worker 仅在 Host task 未结束时运行，共享 stop event；关闭时先置 stop，再等待三个任务结束。任何 Worker 构造失败均阻止 ACTIVE 状态；后台异常进入固定安全状态，不输出业务载荷或秘密。
- 修改 `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py`：验证两个 Worker均启动、共享 stop/Host health、Host正常退出使两者退出、构造失败不宣告 ACTIVE、原凭据/锁/安全异常合同不变。

### B. 当前 C 的真实 P02 与 ProductEvent 控制器

在执行本节前，修改 `scripts/a0v_ecommerce_current_reinstall.py` 与对应测试，增加 C released-owner settlement及 D 的 exact create/prepare/verify/stage/configure/enable 路由：D 只能以前述已收敛的 C 为 predecessor；所有操作继续使用唯一 intent/result 和原正式服务。新 Host 必须先显示 lifecycle、product-event、analysis-data-requirement 三个 Worker ACTIVE，随后才能接收 settlement与 D 的运行请求。切换后本节所有“当前 C”按实际当前安装 D 执行，控制器从主库 current head解析并锁定 exact ref，不能保留 C 常量。

- 新增 `scripts/a0v_qyh_current_product_event_first_chain.py`：固定仓外0700状态目录、0600 intent/result；分 action 执行 observe、source-probe、prepare-p02、select、control、schedule、bind、enable/read/disable、Case/Policy/EventControl 与最终观察。每项在调用前按主库当前事实生成并冻结 intent；已有 intent/result 时只读，不重发。
- 修改 `scripts/a0v_p02_current_preflight.py` 与 `services/aos-api/tests/test_a0v_p02_current_preflight.py`：移除退役 Niushop 1.5/C 之前安装常量，从当前重装 D 的不可变 create receipt与主库 active@5 head导出 exact installation ref；固定当前签名根与 Niushop 1.22，要求 ready/enabled/unfenced、config ref存在并逐字段匹配。当前 P02 mapping与1.5字节一致，但 schema/masking摘要已经变化，必须从1.22签名资产重新导出，不得复用旧审批中的摘要。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_qyh_current_product_event_first_chain.py`：验证 D/ref/hash/epoch 固定、历史引用拒绝、上游只读边界、状态机、未知结果只观察、canary与外部副作用为零。执行组件继续由现有生产 Owner测试覆盖，不复制实现。
- 修正控制器结果分类：HTTP 调用完成不等于业务成功；Run 为 failed 时输出 `CURRENT_PRODUCT_SNAPSHOT_FAILED` 并保留安全 error code，只有真实 Run succeeded 才输出 `CURRENT_PRODUCT_SNAPSHOT_SUCCEEDED`。观察动作增加 Journal/derived/Dataset/claim 的计数，避免把“调用完成”误报为批次完成。
- 后继 Niushop 1.23 只修改 P02 mapping 的时间基础与对应包清单/签名材料；不修改 v2 通用语义，不放宽 `EcomConsistencyStore` 同版本约束。经现有包构建验证、签名和 D→E 生命周期后，重新生成 E 的 P02 current preflight 与控制 refs。
- 若实际盘点证明某一步已有通用正式入口，控制器只做严格装配与证据，不新增第二套 Store/Receipt；若正式入口缺失，先补本方案再进行最小产品实现。

## preHash

- `scripts/a0v_ecommerce_runtime_host.py`：`88935d03f619c2a21a3dea1ef0617c92c3cd8458`
- `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py`：`45e1c4a46692c4de66cbd73fd8196d6f049516e5`
- `scripts/a0v_p02_current_preflight.py`：`44f9a5f4d498955a45fd9672a1ca8fc686d7048e`
- `services/aos-api/aos_api/ecommerce_product_event_worker.py`：`62734cb80f64098f0df7c1b2065619015d5aec53`
- `services/aos-api/aos_api/ecommerce_analysis_data_requirement_worker.py`：`a140200484a694f1684226fbbdd40fa8071adf7e`
- `services/aos-api/aos_api/main.py`：`4d55aa576021b657dade0104c3be3e385482fa6e`
- 新控制器、新测试与本方案：`NEW`。

## 六步退出条件

1. 当前包、来源、历史配置、Host接线和经营资料盘点完成；真实 Source probe 通过。
2. 本方案、范围、preHash、授权与停止条件提交。
3. 独立 Host 同生命周期 Worker接线及测试通过；旧 Host受控退出，C 经正式 disable收敛；D 由新 Host完整安装，唯一 Host与三个业务 Worker健康，D 与三个 OCI连续可用。
4. D 的 P02 SourceSelection/RuntimeControl/ScheduleBinding 通过正式入口持久化；一次新鲜真实只读批次完成，SourceClaim/Journal/Dataset/Projection exact对账，canary为零。
5. 当前 Case、ProductEvent policy 与 Event Control经当前职责/审批门启用；真实批次由 Worker生成 Occurrence和 Analysis入口，不由脚本写成功 Receipt。
6. Case/Run/Task/DataRequirement及来源化分析状态独立读回；幂等复跑无重复对象，Host重启可恢复。落验证证据后进入下一波 exact 三阶段评审与经营计划候选，再承接八工作台内容/能力任务。

## 完成边界

本波成功只证明“当前签名包 + 当前真实来源 + 自然事件 → 分析入口/等待数据或运行态”。经营建议质量、exact 方案通过、内容与媒体产物、人工评审后续跑、总控复盘和 WikiCandidate 需继续按后续波次逐项实测；在这些完成并连续观察前不作发布决定。
