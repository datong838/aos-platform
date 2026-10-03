# W5CB4 E17-s3o-n｜Capability 自定义发行连接的 readiness 显式注入门

日期 2026-10-03。依据 231 长程路线的租户/最小权限与 A1 首链证据、584/585、D-waves s3o-m、CapabilityBinding 和 BindingReadiness 原服务。当前真库只读，隔离 PG135 负例已经实测：独立 Capability writer 的原 evaluate 因默认 readiness 自取 `db_connect` 而使用 `aos_app` owner。不能把这个 owner 兜底当成受限发行成功。

## 本波边界与文件

1. `services/aos-api/aos_api/aip_capability_binding_service.py`：只对显式传入自定义 `connect_factory`、却没有显式 `readiness_service` 的实例，禁止 `preview`、`evaluate` 和进入 active 前的 readiness 复核；在任何 readiness 数据库读取前失败关闭。默认预览服务的既有构造和 create/replay 保持原样，非 active 的受限写命令不扩权。不得把 writer 连接隐式用作 reader。
2. `services/aos-api/tests/aip/test_e17_s3om_capability_reader_pg.py`：先增原服务 RED，验证自定义 issuer create 后，evaluate 在 `aos_app` 读取前被拒、无 evaluate Receipt、Binding version 不变；另证 preview/active 不能绕过。保留原严格 xfail，直到正式只读身份及原 evaluate 正向齐备。
3. 本文件与同名 verification；波次末精确提交代码、Task/Delivery 与 01/06/D-waves/续接。不存在当前权威数据库 ACL/迁移或 Host/worker/Provider 变更。

## 验收与下波

先 RED 再最小实现；隔离 PG 跑 s3o-m/s3o-l 及相邻 Capability tests，核幂等 create、跨租户、无半 Receipt，静态及 diff check。此波只达到“不再通过 owner 悄悄读取”，不宣称 evaluate 正向或首链。下一波盘点全局 CapabilityRevision 与租户 Model/Policy/Gate/Evidence 读取表，建精确无写权、非 owner、private credential 的受限 reader；Service 显式注入后，再扩 issuer UPDATE 并完成原 blocked evaluate/CAS。当前库切换仍需全备、ACL-faithful 克隆、零执行窗口。
