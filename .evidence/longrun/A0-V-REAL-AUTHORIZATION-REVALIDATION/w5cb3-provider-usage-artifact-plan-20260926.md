# W5CB3｜exact 内容命令到 Provider／用量／可读产物施工方案（执行前）

## 上位目标与现场

- 复习 231-5 §1/4/6/7、231-9 BG-04、栖月汇数字同事产品方案：首链必须由当前批准和预算约束下的内容任务自然调用能力，得到含真实商品、来源、正文、渠道与约束的可读草稿，再交人工评审；`PENDING` 或空 Artifact 不是业务结果。
- W5CB2 `24296a8a` 仅证明 default-off 的 HELD＋Journal PENDING＋Runtime Receipt 代码门。现有 `CurrentContentRunner`、`ContentExecutionWorker`、`ContentResultConsumer`、`ContentUsageRecorder`、`CurrentContentStatusReader` 已分别实现当前权威准备、唯一 ProviderRequestReceipt 后外呼、结果持久化、measured Usage、预算结算与 Artifact 读回，但未以 W5CB2 exact 命令在同一完整 schema 贯通，不能据组件测试声称自然链成功。
- 生产 `a0v_104` 未应用，Worker/Provider 未启。旧 12 Run、230 L0、商城源读保持原边界；不为旧数据逐行补证阻断此核心代码波。

## 文件级最小清单与顺序

1. `services/aos-api/tests/...`：先用 W5CB2 命令合同建立隔离 PostgreSQL 同库测试，从 HELD/PENDING 经正式 ProviderRequestReceipt、可控的非外网 invoker、Journal、measured Usage、Budget settled/cost_pending 到可读 Artifact／StatusReader；另验 `dev-org/dev-project` 为零、重启/未知结果不重发、缺当前来源/批准/价格不提交。缺失的公共 fixture 可独立建在测试文件，不改生产数据。
2. 先运行 RED，定位实际合同断点；只在证据指向时最小修改 `ecommerce_content_execution_composition.py`、`ecommerce_content_execution_worker.py`、`ecommerce_content_result_consumer.py`、`ecommerce_content_usage.py` 或公共预算/Journal 代码。保留唯一提交边界、作用域、当前权限和 no-resend 规则；不得伪造 Ref、批准金额、来源或 Provider 回执。
3. 专项测试、邻接回归、完整 schema 隔离 PG、`alembic heads`／静态检查；浏览器仅在页面有变化时验收。复审代码和 231-5/231-9 合同一致性；记录不能通过的生产激活硬门，不把测试夹具当真实业务。
4. verification 文件落盘后 m1 精确提交；同步 D-waves、AOS Authority 与独立 Prime 投影。若测试找到需要超出本波授权的真实外部调用，则保持 default-off 并继续非副作用实现。

## 退出与下一波

- 本波最多证明同库命令→唯一 Provider intent→受控结果→measured Usage／预算→可读 Artifact 的代码链。正式激活仍需 W5CB2 留下的完整 Handoff→容量→预算同库链、当前安装/审批/价格/来源与独立 Receipt；不得用代码绿替代。
- 下一波 W5CB4 接内容人工 Review、TaskRun 终态与反馈续跑；任何未知提交冻结、只读对账，不手工 `run_definition` 或第二次外呼。
