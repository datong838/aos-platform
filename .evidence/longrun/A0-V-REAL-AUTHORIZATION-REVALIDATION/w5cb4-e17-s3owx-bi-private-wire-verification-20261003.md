# s3o-w-x 第一切片 verification｜BI 私有线协议

- 基线 `m1@1bb8ce98`、Authority `AOS-001238`。上位 231-3/231-9、619–621、D-wave 和 `aip_network_issuer_ipc.py` 已读；先落文件级方案 `w5cb4-e17-s3owx-bi-private-wire-plan-20261003.md`。RED：`test_aip_bi_plan_issuer_ipc.py` 缺模块，exit1。
- 新模块只复用现有内核 peer 与有限帧 primitive；严格 version1、prepare/rebind、Pydantic extra forbid 和重复 key 拒绝；在解码/调用显式 handler 前先核不同 UID 的 peer 和精确双租户。每连接一命令，响应仅固定 status，错误统一 blocked，不返回 JWT、Receipt、actor、DB 细节；发送失败不重试。
- `tests/aip/test_aip_bi_plan_issuer_ipc.py tests/aip/test_aip_bi_plan_issuer_service.py tests/aip/test_aip_network_issuer_ipc.py tests/aip/test_aip_bi_plan_issuer_connection.py`：35 passed，exit0；编译、`git diff --check` 另核。测试中的人工 peer 是线协议单测，不能算真实跨 UID、OIDC、DB 或业务正向验收。
- 方案/代码一致性：没有启动新进程、接 API 默认 HTTP、读写当前库或放行 Host。当前真实正式身份/六 active Agent/四受限函数 ACL 仍缺，HTTP503、首链 pending。本波无 UI/进程/当前数据变化，浏览器不适用；最近真实浏览器三 blocker/无业务入口的已有证据仍有效，不是本波新证明。
- 下一切片：有限 BI Unix 进程配置/启动门，独立 UID/kernel peer、0750 socket 目录、0700/0600 attempt/凭据、每请求外部 OIDC 与 s3o-w-w 受限 DB 工厂显式注入；再做真实跨 UID 和签名隔离 full schema 原 Plan/Receipt/未知提交恢复。正式当前库迁移另需新全备、克隆全链、零执行窗口。
