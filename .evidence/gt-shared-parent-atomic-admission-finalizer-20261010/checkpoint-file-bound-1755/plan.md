# 检查点文件上限修复方案

Rules：231、Task/Lease 单写、原观察器身份/权威/文件校验；不修改观察器上限或产品代码。

RED：当前 Main checkpoint evidence_files 超过32条，本次原唤醒命令拒绝 invalid file list。
候选一：固定验证函数语义闭包与完整八节点 Receipt，已登记隔离实现授权，依赖完整原 Source/事件/原生包/COMMIT 验收。候选二：修复现有检查点文件清单，已登记 Main 证据范围授权，依赖当前 authority1755 和有效唯一 Owner Lease；选择二先恢复接续门。

修改精确文件：Main checkpoint.json；本目录 history-index.json、checkpoint-before.json、verify.py、verification.json。保留完整历史清单及每项文件SHA256，当前清单保留最新16条+历史索引；代码清单不变。Model Task 也有37条，当前 Main Lease 不包含其检查点；保留原状，后续须其有效 Lease 与精确范围处理。其余两个检查点14/10条。

验证：原检查点确实被拒绝；修复后原 checkpoint_snapshot 接受；错误 thread/owner/authority/范围各被原校验拒绝；索引全部历史hash一致；原唤醒命令成功。仅观察信号，不宣称业务完成或整任务交付。
