# W5CB4 BG-00ac｜Skill Eval 报告与 Gate 同事务边界审计方案

复习 228 G2.2、231 首链、BG-00v/w/y/z/aa/ab 和当前 `aip_eval_runner.py`、`aip_eval_authority_store.py`、Report/Gate schema 与 Skill publish 消费者。目标是只读确定能否把 BG-00ab reader 最小接到现有 runner，而不破坏非 Skill Eval；本波不编码、不调用正式执行、不写当前库。

逐文件列明 Run 创建/转态、Target/Judge 执行、Report 写入、Gate 判定各自的连接与提交点；检查 Report case 结构是否能回链双签名 Receipt、Gate 是否强制回读证据、Skill 路径是否已失败封闭。若不存在同事务边界，给出下一波最小独立持久结构/迁移与安全切换要求，不在当前库直接扩表。以 `rg`/文件行号及当前库空 authority 为证；结果登记 D-waves、上下文和 m1 精确提交。
