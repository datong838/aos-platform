# W5CB4 BG-00bu｜a0v116 网络 active 数据库写门与当前实例安全切换方案

## 权威与目的

按 AGENTS.md、aos-engineering-delivery、231/231-4/231-5、41 网络方案及 BG-00bo/bt 复习。BG-00bt 已在 test-only 证明 `aos_runtime` 能绕过应用 Store 直接插入 active NetworkPolicyRevision；当前真实库 `aos_current_preview_20260927@a0v_115` 无正式网络元数据/Proposal/审批，Host关闭。本波只增加默认拒绝的数据库 active INSERT 门，避免 API/Store 与 DB 边界不一致；不接正式批准消费，不用 test-only 事实冒充真实通过。

## 文件级方案和 RED

1. `services/aos-api/tests/aip/test_aip_network_policy_active_db_gate_pg.py`：先在 test-only a0v115 克隆证明 runtime 直接 active INSERT 成功（RED），随后 a0v116 证明 active 同 SQLSTATE `23514` 拒绝、零 head/revision/receipt 持久行；draft INSERT 旧路径仍可在同一事务中成功并 rollback；跨租户仍由 RLS 限制；迁移重跑头一致。无真实库测试写。
2. `services/aos-api/alembic/versions/a0v_116_network_active_insert_gate.py`：从115线性加 `BEFORE INSERT` trigger，仅当 `NEW.lifecycle='active'` 抛 `NETWORK_ACTIVATION_CONSUMPTION_REQUIRED`，其余不变；函数固定 `search_path=pg_catalog`，PUBLIC 执行权撤销，downgrade 拒绝静默移除。消费者未来只能经另波修订数据库门并添加原子消费证明。
3. `scripts/a0v_current_preview_http.py` 和对应小测试：最新代码期望 schema head 116。只改精确常量，不修改启动、worker、Host 或自动迁移逻辑。

## 当前实例迁移硬门

先克隆演练，不直接动当前：确认 m1 唯一写者/签名 Receipt/权威命名卷与 PG 身份、当前115和代码116，核最近备份；停 API/Web/Host/worker/Provider 达零执行，查 8080/8434/18181 全无监听及 PG 其他会话为0；此时做新的 `pg_dump -Fc` 0600、SHA256、TOC。新建第二独立 test-only 库从该 dump 用 `pg_restore --single-transaction --exit-on-error` 全库恢复、验证控制表 count/hash 和115头，克隆115→116、正负 SQL 与控制表复核。只有以上全 GREEN 且备份可读/恢复，才对精确当前库执行单步115→116。迁移后只读核 trigger/head、当前安装/制品/绑定 digest 不变，再用原命名卷和最新 m1 代码重启 PG/API/Web；Host/worker/Provider继续关闭，健康、八工作台 HTTP、安装与租户隔离回读。失败保留备份和克隆，停止切换；绝不删库/卷/备份或重放旧 Run。

## 退出条件与下波

test-only 与当前都证明 runtime 直接 active 写被数据库拒绝，draft 既有路径不受影响；当前真实网络策略行/批准仍0，安装与签名一致。专项/相邻回归、方案复审、verification、01/06/D-waves、authority与 m1 精确提交。BG-00bv 再独立设计正式元数据来源和一次性审批消费；当前库无这些 authority 前仍禁 Host/自然首链。
