# SC4-5l6m exact fence 前序回执验证

Rules：m1 单写，先方案，最小修改，不 push、不迁移主库、230 L0 挂起。

基线 1043c2de，方案 edd4dff5。Task Receipt：SC4-5L6M-EXACT-FENCE-20260916。

第 1–3/6 步：核对提交、强一致记忆 CURRENT、validate GREEN，补方案。

第 4/6 步：新增 missing_receipt/case/snapshot 三个真实 PG 负例，修改前均 DID NOT RAISE（3 failed）；修改 SQL 后均拒绝且完整分派快照和 shrink Receipt 数量保持不变。服务端绑定唯一前序 fence、同 scope/安装/版本/业务目标/快照，并重算前序 canonical hash；收缩回执保存 priorFenceReceiptRef，重复请求返回原 Receipt。

第 5/6 步：隔离 PG 18434（aos_test_admin 下临时 schema），event_control_dispatch_lifecycle_pg + event_control_dispatch_lifecycle + ecommerce_growth_cutover_pg：81 passed，1 skipped，7 既有警告，19.82 秒，退出码 0。另有既有 JDBC shutdown logger closed-file 提示。跳过项不算通过。git diff --check 通过。

第 6/6 步：只关闭 exact fence 前序缺口；未证明完整 Service 签名审批集成、在途 drain、可选组变化后 resumed disable/detach 组合，更未完成真实八工作台验收。无主库/Registry/真实安装修改。下一波：排空条件与并发入场锁；随后正式退出组合测试。
