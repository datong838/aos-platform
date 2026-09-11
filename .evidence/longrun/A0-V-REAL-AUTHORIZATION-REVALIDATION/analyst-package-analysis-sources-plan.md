# 经营参谋包内分析来源合同切片

基线 `m1@23ecdc29`，2026-09-11。依据增量清册下一项，把 `ecommerce_analyst_analysis_sources` 中不依赖数据库的请求与材料完整性规则迁入 ecommerce-growth 包。源文件 preHash 为 `e3b2bec141e929e2c7aa6d69227cf7c042359be744caa1ba129c54b8bc10467a`。

包只接收宿主已经完成当前租户、TaskBrief、EvidenceBundle、Disclosure、freshness、revocation 与 marking 校验后返回的材料；包再次校验 exact bundle/evidence refs、grant 全量覆盖、原顺序、payload hash、cutoff、Disclosure identity/expiry 和总字节上限。包不导入 `aos_api`，不连接数据库，不读取凭据，不签发 Disclosure，也不产生 Provider 或运行授权。

本切片新增包模块、独立导入与正负合同测试，更新增量闭包和证据。宿主公共 source port、当前 Owner 读取、成功 Attempt 原 query 重建和正式 Eval target 装配继续作为下一切片；不新增 API、路由或安装激活，230 L0 挂起。
