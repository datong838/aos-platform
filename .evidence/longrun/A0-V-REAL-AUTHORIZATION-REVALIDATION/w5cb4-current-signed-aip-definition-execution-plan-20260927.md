# W5CB4 当前 signed AIP 定义正式发布执行计划（2026-09-27，编码前）

## 目标/上位边界

- 归属 231 主线 A0-V/BG-00 与 A1/BG-04 的最小接线；满足栖月汇产品方案 9.3 “建议绑定精确数据、策略、版本和证据，未 ready 失败关闭”。此波只把已签名 growth `1.11.0` 内的 6 Agent、37 Skill、10 Capability 定义发布到当前新库；不创建 AgentInstance、Skill/CapabilityBinding、Runtime binding，不启 worker/Host、Provider 或业务动作。
- 当前前置 `833ac36d` 的只读 proof 是时点证据，不是永久授权。正式写前同进程重核当前库、RegistrySnapshot、TrustRoot、签名、contentHash、目录内容两次；目标必须是 `aos_current_preview_20260927@a0v_106`、唯一 approved 安装、Runtime binding=0。
- `m1` 唯一写者，不 push。旧 `1.3.0`/source `1.2.0` 的发布/选择行为不可回归；当前包不能借旧版本名发布。开发代码前不读商城源数据，不碰原 12 Run。

## 文件级实施清单

1. `services/aos-api/aos_api/aip_solution_pack_publisher.py`：抽取共同的 6/37/10 合同验证与 payload 计算；新增只接受当前已核签 `1.11.0` 的显式发布入口，source `ResourceRef.revision=1.11.0`。旧 `publish(1.3.0)` 保持原来源和公开语义。当前入口不能凭裸目录自动获得发布权。
2. `services/aos-api/aos_api/aip_ecommerce_agent_installer.py`：完整来源单选。优先当前 `1.11.0` 的精确完整 6/37/10；当前零行时兼容完整旧 `1.2.0`；任一来源部分/重复/跨来源冲突时 fail closed，绝不拼凑。历史已安装实例不自动改绑。
3. 新增 `scripts/a0v_current_aip_definition_publish.py`：调用当前 exact 前置，在任何写前只读枚举目标键与当前三表；若全零可一次开始，若全量 exact 已在则只报告已完成；若部分或冲突停在只读对账，绝不重发。执行写入后逐键读回身份、hash、source 与 6/37/10，证据 JSON 只保留非秘密摘要；异常或未知提交边界输出冻结状态且不自动重试。
4. `services/aos-api/tests/aip/test_aip6_ecommerce_solution_pack.py`、相关 installer 单测及新脚本纯/隔离 PG 测试：旧来源兼容、当前精确来源、混合/部分拒绝、错签名/版本/哈希、异常后只读冻结、全量回读；不可把 fixture 绿当当前库已发布。
5. 本目录 verification 记录 exact 前置/当前库写前写后/单测/累计/安全 HTTP 或浏览器只读回读、未启用 Runtime 和下一门；交叉更新 `docs/palantier/AOS项目开发上下文/227`、`228`。代码变更先最小实现，专项通过后再作当前库写入；任一强一致记忆投影漂移则停止依赖记忆的状态变更。

## 顺序与停止条件

1. 再核强一致记忆、当前 HEAD/工作树、当前库零行与 Host/Cron/worker 关；准备 exact Task Receipt/Lease。
2. 先实现无写选择/计算和隔离测试；所有旧测试通过。当前新库写入前复核 signed receipt 与 `833ac36d` proof 的 exact 值。
3. 单次受控发布 10 Capability→6 Agent→37 Skill；每个 Owner 原生幂等冲突规则保留，但脚本遇未知结果绝不隐式二次调用。部分提交只读冻结，另起正式恢复方案，不在本波“凑齐”。
4. 全量 exact 回读后再验安装页六角色投影；此时仍 `not_prepared`，八类 Runtime 配置和真实 binding 未齐，不启自然执行。verification 落盘、m1 提交，自动进入 BG-00 配置/绑定的下一最小波。

## 实施中波界收紧（本次 adapter 子波）

- 当前发布是 53 个 Owner 独立行写入，现有接口虽按键幂等，跨行不是一个事务；用户对未知结果/部分提交要求绝不重发。故先独立封存“新旧来源发布器适配 + 安装器完整来源单选”的代码子波，本次不提供执行脚本、不写当前库。上述第 3–4 步移到下一个带唯一 intent、部分行只读对账的执行子波，不能把 adapter GREEN 说成发布完成。
- 当前测试套件中 `test_aip6_agent_control_api.py` 的共享夹具引用已不存在的 `.aos-recovery-20260913/state/...` 根目录，在进入测试体前失败；不恢复旧卷、不以此错误推翻 23 项不依赖旧根目录的专项绿。下一波需在当前隔离环境修夹具输入或另建当前专用集成用例，保留原套件失败登记。
