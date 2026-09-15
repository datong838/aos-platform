# 第 3/6 步：真实 canonical 回执交叉验证

2026-09-16；方案基线 `47393077`。Rules：m1 串行、先方案、最小修改、自测落证据、不 push、230 L0 挂起。

移除分派生命周期 PG 测试中的 `$1::text` 哈希占位函数。现在直接从 228asset0 原迁移读取唯一 canonical 函数定义，在测试 schema 安装原实现并固定其递归 search_path。数据库产生的每份 expand、fence、shrink、replay 回执均与 Python canonical_sha256 比对 requestHash 与 contentHash；新增中文身份与嵌套 installationRef 的保真测试。

18434 独立临时 schema 测试 `4 passed`，`git diff --check` 通过。测试使用实际数据库 CAS，结束后清理其自有 schema；没有迁移或修改主库。该结果关闭此前“测试占位哈希无法证明 Python readback 一致”的缺口，未证明签名/审批 Service 完整组合，也未关闭 exact predecessor、drain 与 resumed disable/detach 兼容问题。

下一施工项：补充 exact fence Receipt 和排空的正式协议，先失败用例再实现；继续第 3/6 步，暂不安装或发布。
