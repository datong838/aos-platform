# W5c5h Host 排他权威缺口设计波方案（2026-09-25）

上位 231 A0-V/231-9 BG-00；W5c5g 证明时间和局部门不能合成全机授权。现有 `ar1_003` 目录仅保存 assignment，`a0v_ecommerce_runtime_host.py` 的 `flock` 仅限本机文件系统；本波先把跨机器排他性威胁、DB 侧可实现合同和迁移顺序定稿，不在旧代自然失败现场直接改 Host/Owner。

## 文件级九步

1. 复习 AR1-c Host selector/directory、A0-V 进程/DB 角色、`a0v_091` 严格关闭门及当前 no-effect 边界。
2. 文件清单：本方案；新增 `w5c5h-host-exclusion-authority-design-20260925.md` 设计证据；本 verification。生产 Python/迁移零改。
3. 定义“可证明”的范围：租约 token/epoch 必须由 DB 原子授予，所有受管 Host 进入租户 worker 前验证，续租/失效/接管应有 fencing；目录 assignment 不是 live lease，本机 `flock` 不是全机锁，`ps`/`pg_stat_activity` 不是未来排他证明。列迁移/Host/worker 分波，不在本波启用。
4. 专项静态审计现有表/API/脚本及测试，证明不存在可替代的 DB Host live lease；不得把审计结果写成 GREEN。
5. 跑受限 Host/directory/closure 相关回归；隔离测试库若启则停用。
6. 浏览器只读验收整组停用，页面不提供 Host 排他证据。
7. 复审设计不破坏已运行正常功能：新表 additive/默认空，旧 Host 在未切换前不被误判已受保护；历史旧代关闭仍须单独方案和新鲜权威，不自动借未来迁移放行。
8. verification 先提交，再 CAS 同步 docs/AOS 项目开发上下文和 Prime 独立受管记忆、读回。
9. 下一波 W5c5i：实现 additive DB Host 排他租约基础与隔离 PG 合同；不启用生产 Host，后续再分波做 Host/worker fencing。

m1 单写不 push；不读商城源行；旧 attempt 不补跑；230 L0 挂起；dev-org 零 canary；未知冻结。
