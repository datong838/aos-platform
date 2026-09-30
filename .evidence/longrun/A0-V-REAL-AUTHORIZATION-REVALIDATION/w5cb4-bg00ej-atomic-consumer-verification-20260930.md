# BG00EJ 原子消费验证

基线：m1@00a48808 / AOS-000998。方案/SQL复审完成，进入精确提交与上下文收口；本文件不是正式部署或首链通过证明。

## 新鲜验证

工作目录 `services/aos-api`：

```sh
.venv/bin/python -m pytest -q tests/aip/test_network_atomic_consumer_pg.py tests/aip/test_network_consumer_boundary_pg.py tests/aip/test_network_approval_precheck_expiry_pg.py tests/aip/test_aip_network_policy_action_producer.py --tb=short --show-capture=no
```

最后执行句柄70370，终态退出0，45 passed，7项既有warnings，34.00s。标准fixture创建一次性PG并从迁移头升级；没有运行当前真实数据库迁移。

- 正向：真实Producer/独立隔离Issuer批准后，consumer函数同事务落head/revision/Receipt，既有Store读者可读active；两线程同请求返回唯一Receipt；外层事务失败回滚三类写入。
- 负向：scope不一致、跨租户、错误Event、当前checker成员删除、完成Receipt换Event、runtime/issuer直接调用、撤回记录、Network head漂移、Egress head漂移均拒绝。
- 时间：真实checker行锁等待通过pg_stat_activity证明，跨Proposal/Approval到期后消费拒绝；没有替换时钟。
- 权限：两角色非特权、无membership、无表所有权；caller无检查表DML，owner只有Network三表INSERT；逐列核验全public可见表UPDATE许可，仅固定锁列与head三更新列。
- 迁移：历史网络批准记录要求独立对账；caller LOGIN和owner membership漂移先RED两项缺ROLE_PREFLIGHT_SQL，再最小加迁移前检查，累计GREEN。
- 原runtime/issuer伪造activation Receipt、原runtime直写active仍拒绝；普通publish Receipt不受影响。

## 真实库只读回读

```sh
docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -X -v ON_ERROR_STOP=1 -U aos_app -d aos_current_preview_20260927 -Atc "BEGIN READ ONLY; SELECT current_database(),version_num FROM alembic_version; COMMIT;"
```

退出0：`aos_current_preview_20260927|a0v_118`。代码120尚未部署，119/120必须走独立备份/克隆/零执行窗口波，不能称当前实例最新。

## 排障与未完成

早期RED包含函数缺失、SQLAlchemy误解析JSON绑定参数、psycopg字面百分号、局部变量/列歧义及JSON运算符优先级。修复未变更既有119迁移。曾在仓库根误执行`.venv/bin/python --version`退出127，随后测试均在services/aos-api正确目录执行。

已读现有withdraw路径：AipActionStore.withdraw先锁Proposal FOR UPDATE，与消费相同Proposal串行；当前撤回测试直接隔离插入撤回记录用于覆盖函数拒绝分支，不等于正式用户撤回端到端验收。

复审：固定四参数不接收候选正文；SECURITY DEFINER固定pg_catalog路径，所有表/辅助函数显式public限定；owner无登录或成员入口，caller只有函数EXECUTE；租户GUC需与参数一致且owner独立RLS；Proposal锁与既有批准/撤回路径串行。相同请求已有Receipt仅对账，不重新授权。不同Proposal争用新head由唯一键拒绝，客户端不得把冲突解释为成功。未增加UI或HTTP入口，浏览器验收不适用于此内部SQL切片。`git diff --check`退出0。

无真实consumer凭据或服务入口，当前Egress/正式批准/八类配置/Host/自然首链仍pending；不将隔离测试身份当正式授权。下一波BG00EK接精确消费者连接预检与服务入口方案；当前真实库部署另立备份/克隆/零执行安全波。历史withdrawal与消费并发的产品语义、已有head追加修订正向及最终写入等待跨到期的进一步联合验证随服务接线补齐，不宣称已完成正式端到端验收。
