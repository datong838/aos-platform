# AR2-7D D1 规范库全集读取接续施工卡

- 2026-09-09 接续基线：m1@fa0612c53fe220257c133de15bed02c01a5d1def；AOS-000571 强一致投影 CURRENT、validate GREEN；沿用 ACTIVE 的 AR2-HOST-WIRING-CUTOVER-PLUGGABILITY-BROWSER-ACCEPTANCE Task/Lease（2026-09-18 到期）。
- 复习依据：closure-manifest 第 3～5 节、dynamic-reference-phases、231 总控与 231-6 首部已有全集读取施工卡；原测试尚未跟踪且实现不存在，作为上次未完成工作接续，不删除其他未跟踪文件。
- 新增 `services/aos-api/aos_api/ecommerce_canonical_population.py`；接续 `services/aos-api/tests/test_ecommerce_canonical_population.py`。不改现有读取者、查询结果哈希、路由和持久表。
- 输入仅受信 HostTransaction、TenantScope、三条当前选择 exact ref 和固定对象类型元组；READ COMMITTED 拒绝，同事务 read_bound 核对选择后以完整物理范围参数化查询。固定取 100，达到 100 即拒绝，不截断为成功。
- 输出仅当前规范库有效对象的完整身份、payload_hash 引用与混合语义 source_updated_at。身份使用 `ecom/v1:` 加六元 JSON 数组，防止分隔符碰撞；不读取 payload，不把该时间称作采集时间、历史截止时间或业务新鲜度。空集合允许读取但不意味着履约。
- 增补输入类型、未知对象类型、无店铺、重复身份、错租户/店铺、非法哈希/时间的失败关闭；验证 SERIALIZABLE/REPEATABLE READ、99/100 边界、确定性身份和相邻选择逻辑。
- 风险与回滚：当前表只能证明当前规范库集合，不能证明远端全量、历史人口或采集完整性；实现未注册进运行服务，回退新增读取模块即可，不改数据。后续独立补采集来源、业务窗口与固定规则，不能先挂到 DataFulfill。
- 闭包复验修正范围：清册原 source 单元格使用裸文件名，在包内出现同名模块后验证器无法唯一解析；将其明确为原平台完整路径，保留历史 preHash。补登记既有包内新增编排节点、runtime adapter 与本次读取者的唯一归属和接续基线哈希；不修改验证器或放宽阶段条件。新文件无历史 preHash，明确记录 NEW 与本次实现哈希。
- 验证顺序：缺模块 Red → 实现/专项 Green → 邻接回归 → 闭包阶段检查及差异检查 → 证据与本地提交；无页面修改，不制造浏览器链路验收证据；不 push。
