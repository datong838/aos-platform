# SC4-5l6k E 代真实商品快照与 ProductEvent 自然触发方案

日期：2026-09-15  
基线：`2e6b9291`  
owner：`m1`；不 push；230 L0 挂起。

## 当前事实

E installation `1c08edfb-ec0d-4abb-a411-7b6ec0d6066a@5` 和 generation `ebaa620a-8831-4c2a-b971-788383f352f8` 已 ready/enabled/unfenced，新 Runtime Host 已加载 Niushop 1.23 签名根。P02 的 E SourceSelection、RuntimeControl、ScheduleBinding 已落库，Schedule 仍 disabled，canary claim 为零。

18181 当前 PID `40240` 虽健康，但其 `a0v_product_controlled_api.py` 仍固定上一代 `signed-bundles-current-ecommerce` 根。API 与 Host 资产根不一致时禁止触发真实 Run。

## Rules

1. 先切换受控 API profile 并完成静态/真实 preflight，后触发源读取；只改产品私有 profile，原诊断 launcher 不改。
2. API 继续固定 `127.0.0.1:18181` 和主库 `aos_meta_head`；迁移、第二 Runtime Host、QYH Cron、AIP 自动任务、模型健康维护、SSH 预热均保持关闭。
3. 只在确认 18181 唯一监听 PID 的命令行与当前已知启动器精确匹配后发送 TERM；端口未释放或新 preflight 失败即停止替换并诊断。
4. 真实 Run 只用 E 新控制引用，Schedule 在触发前 disabled，临时 enable 后只运行一次，并在 finally 恢复 disabled。一个 Run 只允许一次源调用。
5. 返回未知或失败时先读原 Run/Receipt/stage，不换 key、不再触发；历史 D 失败 Run 永久保留。
6. 成功至少要求 Run succeeded、executor_stopped=true、command/derived/dataset 各 1、recovery claim 0，Dataset 中 65 行 Product 以 observation 版本 materialize；checkpoint 与 Receipt 自洽。
7. ProductEvent/Case 必须由 Worker 从 Dataset 自然消费，不直接插入、不手工调用内部 Worker 方法；等待后若未出现，记录正式缺口并停止该阶段写动作。
8. 正租户固定 `org-org/dev-project`；`dev-org/dev-project` 只能作零写 canary。无商城写、发布、触达、投流、改价、库存或履约副作用。

## 文件范围

先修改：

- `scripts/a0v_product_controlled_api.py`：产品 API 固定根切到 `signed-bundles-niushop-1.23-current`。
- `services/aos-api/tests/test_a0v_controlled_api.py`：验证产品 profile 新根及所有关闭标志不变。

仅在真实观察暴露正式缺口后，才另补方案并新增最小代码；不得为做绿预先改 Dataset、Receipt、checkpoint 或 ProductEvent Worker。

## preHash

- `scripts/a0v_product_controlled_api.py`：`b3443827a6fd8762b29bba5670c193a933517d8d8644a5620d7fc9a05a181e21`
- `services/aos-api/tests/test_a0v_controlled_api.py`：`aa0e8660a25fc9536139ff3a2d28514dd10a24a05fe52a46e5929f6c05462f63`
- `scripts/a0v_qyh_current_product_event_first_chain.py`：`e95da497189672a10758c08263f680be4f81b070d4454f76c9d1b31d289262f2`，本波起始不修改。

## 六步退出条件

1. 执行前 E refs、Schedule、Host/OCI、历史失败 Run、API 旧根事实冻结。
2. 本方案、切换边界、唯一 Run 和停止条件提交。
3. 产品 API profile 切到 1.23，新旧静态测试通过；旧 PID 优雅退出，新 PID preflight、health、ready 通过。
4. 唯一真实 P02 Run 完成；Schedule 恢复 disabled；Run 与 ingress 三阶段、65 行 Dataset、Receipt/checkpoint 精确读回。
5. ProductEvent Worker 自然创建且只创建预期 Occurrence/Case/Run，sourceRefs 指向本次 Dataset；canary 零写。
6. 落证据并提交。若第 5 步成功，下一波进入数字同事分析与来源建议；若失败，下一波只修复已证实的自然触发缺口。

## 完成边界

本波最多证明“真实商品数据更新自然进入 Dataset 并触发 ProductEvent/Case”。它不提前宣称数字同事分析、exact 方案评审、内容任务、能力执行、产物、人工评审续跑、复盘、Wiki 或八工作台全部完成。
