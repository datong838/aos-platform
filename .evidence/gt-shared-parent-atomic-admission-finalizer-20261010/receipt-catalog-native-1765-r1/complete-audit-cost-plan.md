# 完整 native catalog 审计成本调查
本轮延续已登记 Main Receipt 成本候选；完整 catalog 组件原 Task 同 owner ACTIVE。只新增本目录 complete-audit-cost.json，不修改产品代码或既有失败记录。
此前 retained fixture 的 FACT 为新体、PAIR/EVIDENCE 已恢复旧体、INSTALLATION 已删除，因此不能用该混合状态声明完整审计耗时或成功。本步在独立 admin 原生事务临时安装固定完整家族，逐字节确认后，以原 publication Owner 调用 INSTALLATION 三次，取得 native 函数统计。所有 DDL/ACL 及安装副作用通过实际 rollback 撤销，再从新连接对账全部函数/ACL原样，禁止签名、Source 重发或时限延长。仅对保留隔离库执行，不触碰真库。
原测试清理 exact_public_source_caller 删除 INSTALLATION，physical 测试恢复 legacy PAIR/EVIDENCE，却无 catalog FACT 恢复，构成可复现混合身份；后续新夹具必须保存并恢复 FACT，同时使新完整家族生存期与原 Source public entries 一致。teardown 连接失败仍需单独证据，不能凭混合身份推定原因。
首次事务调查识别器拒绝且已自动 rollback：保留库 INSTALLATION 已不存在，版本化 profile compiler 仅替换已安装的私有函数，不承担基础 Owner/ACL 安装。下一次只在同一可回滚调查事务中先调用原 source_public_entry_statements 建立原始安装，再替换完整固定家族；不直接补权限、不把该前提误判为产品路径成功。
