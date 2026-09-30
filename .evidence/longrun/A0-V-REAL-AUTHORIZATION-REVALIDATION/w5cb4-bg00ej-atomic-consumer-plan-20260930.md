# BG00EJ｜受控网络策略原子消费方案

## 接续排障

原专项三项在迁移建函数阶段报 SQLAlchemy bind parameter `true` 缺失；JSON 字面量被 `op.execute` 的文本绑定解析器误识别。函数 DDL 使用连接的 `exec_driver_sql` 原样执行，保持 SQL 语义不变；先复跑原三项，随后继续合同负例与相邻回归，未通过前不收口。

接续实测：驱动执行还需转义字面 `%ROWTYPE`；进入函数后发现 `policy_id` 局部变量/列歧义及 JSON `@>` 两端提取优先级错误，均已最小修复。标准隔离PG执行 `.venv/bin/python -m pytest -q tests/aip/test_network_atomic_consumer_pg.py --tb=short --show-capture=no` 最后退出0，10 passed / 7既有warnings / 5.32s：原子消费与既有Store回读、并发同请求、外层事务回滚、scope/跨租户/错Event/撤销成员拒绝、旧Receipt换Event冲突、runtime/issuer无执行权限。当前仅第4/9步，不代表整波GREEN；未提交、未更新authority、未迁移当前库。下一步补等待跨期限、withdrawal与head/egress漂移、迁移历史门及精确owner权限，然后相邻累计回归和复审收口。现有测试句柄17713已正常退出，无需重启该次测试。

基线 m1@00a48808 / AOS-000998；复习231-1/231-3、BG00EE/EH/EI。目标是BG00EI权限矩阵下的真实数据库原子消费，当前库a0v118保持只读；本波代码新增a0v120，仅在标准一次性PG升级。

## 精确文件

- `services/aos-api/alembic/versions/a0v_120_network_atomic_consumer.py`：固定四文本参数`aip_consume_network_activation_a0v_120(org,project,proposal,event)`，返回原Receipt结果JSON；函数owner为aos_network_consumer_owner，EXECUTE仅caller，固定pg_catalog search_path。增加owner精确SELECT/锁列UPDATE/Network写权限与独立租户RLS，不授runtime membership，不授ApprovalEvent INSERT。
- `services/aos-api/tests/aip/test_network_atomic_consumer_pg.py`：复用EH真实隔离Producer/Issuer夹具；RED缺函数，GREEN验证同事务head/revision/Receipt、并发同请求唯一、回滚不留部分事实、重读相同Receipt；错租户/Event、撤回/到期/成员撤销/目标漂移、普通runtime与issuer直调/直接active INSERT拒绝。
- `services/aos-api/tests/aip/test_network_consumer_boundary_pg.py`：将119阶段owner无DML断言升级为120精确权限断言；caller始终无表DML，owner无Approval INSERT/表所有权，原runtime Receipt伪造与active插入负例仍保留。
- 对应verification、D-waves及接续文档。

## 事务与权限合同

1. migration拒绝任何历史activation Receipt或网络ApprovalEvent，要求独立对账；不回填伪造来源。校验caller/owner非特权及无membership，仍NOLOGIN；凭据部署另波。
2. 函数仅接受与当前session tenant GUC相同的非空scope，session_user须consumer_call；数据库权限而非GUC证明调用者身份。caller不能SET owner/runtime/issuer。超级管理员不在可防御边界。
3. Proposal FOR UPDATE序列化同请求；固定操作名与目标，先按tenant/Proposal/Event/target/binding构造request hash，已有Receipt只读返回，换Event冲突拒绝；不将历史完成重读视为重新授权。
4. 无Receipt时锁定唯一Approval及draft、当前maker/checker、保留的ObjectType/ActionType、Network head、Egress head。检查approved、唯一checker.1、maker分离、版本+1、hash/eligibility、撤回不存在、精确元数据和不可变draft。当前Egress必须head/revision/hash/payload/租户一致、active且有效，网络边界为子集且时间被包含。哈希复用既有canonical_asset_registry_jsonb，不引入第二种序列化。
5. 最终时钟核Proposal/Event/网络/Egress有效期；同事务写head/revision/Receipt，写后再核时效，超时整事务失败。不同Proposal竞争同一新head由唯一键拒绝，绝不覆盖；同Proposal并发等待后只读原Receipt。
6. active trigger只在session consumer_call + current consumer_owner路径放行；consumer_owner无登录或成员可达性，只拥有本固定函数。普通publish(active)继续拒绝。Receipt包含Proposal/Event绑定并固定消费键Proposal ID；失败/未知结果通过原Receipt对账，不重发外部动作。

生产仍需当前正式身份、连接预检、服务入口、迁移完整备份/克隆/零执行窗口。测试合成身份不是正式业务验收；不启动Host/worker/Provider，不读商城源，不创建Run，不push，230 L0挂起。代码仅在完整负向与并发/回滚证明后收口；任何尚未证明的门保留明确pending。
