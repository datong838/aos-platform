# W5CB4 E17-s3f｜签名 Network 来源到配置候选读者文件级方案

## 上位与范围

- 接 E17-s3e，八配置计数仅供引导，不能授权运行。BG00 Network 原 producer/issuer→独立批准→低权 consumer 已在隔离库测试；正式签名身份联测 `test_network_consumer_signed_https_pg.py` 目前只回读 Network Store/Receipt，没有连 `read_candidates`。
- 本波在原签名正向用例前后读取八项候选，核 Network 计数只增加1、其他七项不变；继续保留 token 更新后只读回执、同键幂等与网络三件套原断言。当前权威库只读、Host/worker/Provider关闭。

## 文件级施工

1. `services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py`：沿原 `approved_args`、签名命令、`consume_network_once`，在原消费前后经普通只读租户连接调用 `runtime_configuration_candidates.read_candidates`。不直接插 active，不改原 consumer。
2. 对原 signed 正向和 invalid 身份负例、候选读者做专项及相邻回归；`py_compile`、`git diff --check`；如果原读者误计才另起最小生产修复方案。
3. 落盘 verification、m1 精确提交、AOS/Prime 上下文与 D-wave；下波从剩余五项选不依赖正式 Model Eval 的预算/治理合法来源。

## 证据限度

隔离 Network `+1` 不表示当前实例正式签名 Network 已发布，也不表示其已与 Egress/RuntimePolicy 或安装配置精确绑定。未知结果只读对账，不重发。

## 实测验证

- 原 `approved_args` 来源（原提案/批准）→ HTTPS JWT 签名原 maker → `consume_network_once` 低权消费 → 刷新 JWT 只读回执和同键幂等，原 `counts` 仍 `(1,1,1)`。同一 test-only 全迁移库中，`read_candidates` 读回 `network_policies` 比消费前恰好 `+1`，另外七项计数不变。
- 新增专项退出0：1 passed；原无效签名身份六反例及配置候选读者相邻合计11 passed/退出0；`py_compile`、`git diff --check` 退出0。仅测试文件增加9行，原 consumer/读者生产代码未改。
- 当前权威库未写；全迁移隔离身份和数据仅证明原代码连接，不等于当前签名来源、八配置齐备、精确配置绑定或 Host 可启。下波优先预算/Quota/BudgetPolicy 合法来源与候选读者的独立联测，仍遵守当前真库只读和正式费用审批边界。
