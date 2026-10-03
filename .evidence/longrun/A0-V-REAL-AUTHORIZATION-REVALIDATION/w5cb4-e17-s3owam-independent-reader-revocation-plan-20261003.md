# E17-s3o-w-am｜独立只读 reader 的证据撤销全链

## 上位与边界
231-9、AIP-7 22、BIND-1 31 与 s3o-w-al verification：Data/Tool EvidenceBundle 若 exact 撤销必须在 Binding readiness 拒绝；受限 reader 只读、非 owner、不继承 runtime、仅白名单表及租户 RLS。当前权威库 reader role=0，当前库只读；正式角色/ACL 上线属单独一致备份、克隆全链、零执行窗口波。

## 文件级清单
- `services/aos-api/tests/aip/test_e17_s3oo_capability_reader_pg.py`：复用可销毁 PG 和原独立 reader fixture，写一次 test-only frozen EvidenceBundle；以原 `PostgresBindingDependencyAuthority(readiness_reader)` 正向读取，追加原 exact revoke event 后只读负向；错租户负向。验证 OS/DB 登录仍为 `aos_aip_binding_readiness_reader` 且 read_only=on；撤销表 SELECT 被撤回时 `_require_identity` 失败关闭。
- 先跑目标/相邻测试；如发现真实缺口先 RED，再只改 `aip_binding_readiness_service.py` 或 `aip_binding_readiness_reader_connection.py` 最小点；不改公共 DTO/迁移和当前库。证据落本目录，精确提交。

## 退出条件
真实隔离库证据，不以 fake 代替；可销毁库/角色零残留；正租户受限读、错租户空读、撤销即拒、撤权连接失败封闭；相邻回归 GREEN。当前实例身份缺失只阻当前实例，Host/worker/Provider继续关。
