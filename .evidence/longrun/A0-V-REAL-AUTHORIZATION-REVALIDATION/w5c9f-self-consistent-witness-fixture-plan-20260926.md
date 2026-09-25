# W5c9f｜历史见证“自洽但恶意”输入夹具可行性审计

## 上位边界与转向

W5c9d/e 后原十二 Run 已过时间门仍无全机 Fleet/Owner 权威；W5c7t 证明仓库内无可独立核验的资产/部署全集来源，本波不伪造或自报为真实授权。继续可独立完成的 W5c8r 债：`a0v_098` 见证写门已有隔离 PG 正/负例，但缺“原 claim/input/member **合法提交、彼此自洽而语义恶意**”夹具。真库仍未迁 a0v_096/097/098，operator 未授应用，任何测试 GREEN 不得升级为历史回填/ACK/closure 权限。

## 文件级与验收

- 先审 `services/aos-api/alembic/versions/a0v_097_snapshot_group_canonical_witness_sidecar.py`、`a0v_098_snapshot_group_witness_backfill_gate.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c8q_witness_backfill_gate_pg.py` 与 synthetic fixture helper 的唯一约束/不可变触发器/写入顺序，仅输出结构和无密数据。确认能否在一次性 `aos_test_*` DB 构造独立恶意自洽组；不读取真实历史或商城源。
- 若可构造，先在该测试文件补**仅隔离 PG** 拒绝/承认边界：语义字段若应受见证函数约束，先 RED 再最小迁移修复及单元/PG 回归；若见证函数只保存 canonical 原字节而不授语义 authority，测试必须明确证明“自洽恶意也只得 canonical sidecar，不能作 closure/ACK”，不能把它写成正向授权。
- 若 fixture 因原表不可变/约束无法合法提交，落盘具体约束与安全结论，下一波专门设计构造，不临时改生产约束或真实数据。测试库/临时 caller 角色精确清理。
- 本波不重启 8080/18181/PG，不修改真实租约、迁移、商城源、原 Run/Receipt、Worker/ACK。

## 九步

1. 复习 231、W5c8q/r、W5c7t 与当前原组 no-authority。
2. 本方案先提交。
3. 静态约束/fixture 可行性审计，隔离 PG 前检。
4. 能安全构造则最小测试/迁移修复；不能则 STOP 并给精确阻点。
5. 专项与相关累计，测试 DB/角色残留 0。
6. 复审 canonical 字节保存与语义/真实授权的分界。
7. 8080 业务浏览器离线，不填业务验收 GREEN。
8. audit/verification、m1、D-waves/AOS CAS/Prime。
9. 自动下一波：补剩余 witness/Receipt 负例或另一可独立研发债；外部 Fleet 来源未确认前原组关闭冻结。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push。
