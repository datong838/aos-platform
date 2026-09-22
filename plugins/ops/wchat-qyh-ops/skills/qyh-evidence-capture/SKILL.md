---
name: qyh-evidence-capture
description: Capture privacy-safe, auditable evidence for 栖月汇 admin, mini-program, database, and business investigations. Use when recording screenshots, page observations, source facts, owner explanations, conflicts, freshness, confidence, non-claims, checkpoints, or stop conditions, and whenever another wchat-qyh-ops skill produces a conclusion.
---

# 栖月汇证据记录

先读 [证据卡模板](references/evidence-card.md) 和 [隐私与停止规则](references/privacy-and-stop.md)。

## 原则

> 只记录支持当前经营问题的最小证据；证据证明什么与不证明什么同样重要。

## 证据类型

- `OBSERVED_UI`：页面可见结构或状态；
- `SCHEMA_EVIDENCE`：表、字段、关系或代码结构；
- `DATA_AGGREGATE`：脱敏聚合与口径；
- `OWNER_EXPLANATION`：负责人对规则/线下过程的说明；
- `HYPOTHESIS`：待验证经营解释；
- `RECEIPT/EFFECT`：受控动作及成熟效果窗口。

## 完成门

每项结论必须有 source、scope、collectedAt/cutoff、quality、confidence、支持内容、nonClaims、敏感级别和下一步。冲突不得被平均或隐藏。

## 截图

截图前最小化范围并脱敏；默认不保存包含客户、订单、地址、支付、密钥或个人收益的完整页面。若无法安全裁剪，只记录结构化文字和 EvidenceRef。
