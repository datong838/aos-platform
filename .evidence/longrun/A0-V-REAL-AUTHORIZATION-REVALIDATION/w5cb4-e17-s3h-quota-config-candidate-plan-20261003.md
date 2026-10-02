# E17-s3h 原签名 Quota 到配置候选计划

- 上位边界：231/栖月汇真实动作按当前预算、配额与审批运行；E17-s3g 只证明隔离 Budget/BudgetPolicy。原 `a0v_130` Quota 激活要求独立 maker/checker、签名提案、R2 事件、低权消费者、精确 head/窗口/租户，普通 Store active 仍拒绝。
- 仅改 `services/aos-api/tests/aip/test_quota_policy_activation_pg.py`：复用现有签名正向链，在审批完成、消费前取候选基线，消费后用原 `read_candidates` 核 Quota +1、另七项不变、dev-org不变、旧 Receipt 幂等；负例沿用现有 drift/过期/越权专项。先 RED 后最小断言修正。
- 不改 SQL/产品权限、不碰当前数据库或自然 Run；专项/相邻回归、diff/py_compile、verification、精确提交、AOS/Prime/D-wave收口。候选不等于配置绑定和 Host 准入。
