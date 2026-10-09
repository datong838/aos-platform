# 可信结束协议前置：安装与调用者边界

Rules：231、原实际 COMMIT 合同、唯一 m1；仅本证据目录及已有隔离库 READ ONLY。文件为 register.py、audit_trust.py、trust-audit.json、protocol-contract.md、checkpoint.json。无产品、扩展、数据库内核或全局配置修改。

已登记候选一为原 Source 可信结束协议，依赖精确 current caller/xid、原签名事实、结束通道、无法被普通调用者卸载或改写的门、最后判定与未知终态对账；候选二为 typed Model/Route 完整执行证明，仍依原 joint/唯一 Intent/预算与独立 Owner。先做候选一的安装信任边界前置：核现有 C verifier 的 pg_proc 安装属性、Owner/角色/membership/私有表与函数权限、preload 参数上下文和当前值。只读取目录，不尝试 SET preload/ALTER/LOAD，不据目录推断未知库中 callback 注册状态。

随后冻结协议：普通调用者不能自己选择、提前耗尽或撤除门；原 Source 签名事实先由现有 verifier 校验，事务状态按 native top xid/pid/session 精确绑定，子事务 rollback 清除对应 obligation、子提交合并、整个 abort 清空；PREPARE 禁入及所有实际提交入口单独验证。扩展 callback 原型即使另获隔离安装授权，也只能证明最后可回滚检查，不自动满足 WAL/确认硬截止。严格原要求仍 RED，安全独立开发不停。
