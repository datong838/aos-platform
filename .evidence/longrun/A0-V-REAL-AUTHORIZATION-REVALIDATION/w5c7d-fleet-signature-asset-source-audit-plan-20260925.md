# W5c7d Fleet 签名/资产来源审计方案（2026-09-25）

上位 W5c7b/c：结构验证器固定 no-authority；可信 universe 需要部署控制面签名和全部启动面覆盖，当前没有可用 live 来源。AOS Registry 包签名或 Apollo mock fleet 不可自动改名为 Runtime Host fleet authority。

## 文件级九步

1. 复习 W5c7b/c、231/231-9、Host/worker 入口、资产 Registry/签名 trust-root、部署/IaC 与 Apollo fleet 来源。
2. 本方案先提交；仅新增审计证据 `w5c7d-fleet-signature-asset-source-audit-20260925.md` 与 verification，不改生产/DB/部署/Host。
3. 逐一标明每个候选来源的签名 scope、覆盖面、实时性、可禁止旧入口重启能力；不得把代码资产/签名包、租户目录、Helm 模板、本机 launchd、Apollo mock 视为全机控制面。
4. 对缺口给出可实施的最小后续切片：专用签名信封/固定 trust root 与严格验证器只能验证来源身份；覆盖性仍需独立资产/部署控制面交叉读回。
5. 跑 Host/closure、结构分类器和 W5c5k–z/W5c6a–z/JDBC 累计回归；测试 PG 用后停。
6. 浏览器只读 rev4 停用，不保存/运行/冲刷队列。
7. 复审已实现/未实现/未部署边界，真实 closure 保持 no-effect。
8. verification 后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立记忆并读回。
9. 下一波 W5c7e：先方案，依据审计只实现隔离专用签名信封验证与负例，不接真实 Host/closure；或若来源不存在，先做信任根生命周期设计。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
