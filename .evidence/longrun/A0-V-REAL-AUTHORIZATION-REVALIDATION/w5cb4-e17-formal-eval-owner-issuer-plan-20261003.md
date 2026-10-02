# W5CB4 E17-s3｜正式 Skill Eval Owner、issuer、writer 来源只读审计方案

## 上位与范围

- 复习 231/231-3/231-9、56/64、553–556、BG-00w/ah/aj/ak/am。E17-s2c 隔离 test-only 签名消费正向通过，当前实例仍需原 Run Owner、正式 issuer/Target/Judge 和受限 writer，不能从测试夹具升格。
- 本波只读核 `aos_current_preview_20260927@a0v_135` 的正租户 EvalRun/Report/root/identity/Receipt/sidecar、PG writer role，原 Runner/Writer/预检代码和 `.env` 的配置键是否存在；仅输出键名/布尔，不读取凭据值，不建角色/Run/签名/Receipt，不启 Host/Provider。

## 文件级检查

1. `services/aos-api/aos_api/aip_eval_runner.py`：定位 Skill 双硬拒与原 Run 创建入口；区分正式 Owner 尚无与签名证明消费者已接线。
2. `services/aos-api/aos_api/aip_eval_writer_connection.py`、`aip_eval_writer_authority_preflight.py`、`aip_eval_writer_atomic.py`：核默认关闭的凭据文件、独立 LOGIN/NOLOGIN role、serializable 租户同事务、合法 root/identity/Run 与写入顺序。
3. 只读 SQL 与服务/浏览器回读；在 verification 列精确数量、命令与退出码、候选来源和单实例 blocker。下波 E17-s3a 先方案/RED，在 test-only 建原 Skill EvalRun Owner 入口并证明受限 writer 不得手插，不动当前库；另 E17-s3b 可独立查原 Logic/Route/Policy 生产者。

## 边界

当前真实库只读；org-org/dev-project 正向，dev-org 零写；无假账号/test-only 身份接当前实例，无旧 Run/manual run_definition/商城源/230 L0/push。当前实例缺 authority 时只阻断该实例，长期 Goal active。
