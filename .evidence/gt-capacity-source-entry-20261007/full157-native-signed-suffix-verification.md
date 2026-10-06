# 原事实与登记签名后缀检查点

基线 m1 f57d8b7685707fecf2883019666f2a5ed724de6a / authority AOS-001440。完整长程 Goal 与父 Tasks 持续 active；本文件不是 Source Delivery。

## 本次实现与原合同

仅 publication_transaction.py 追加一个 private invoker 组合函数。原 secret-free command/full facts/withdrawal锁之后，按 registry epoch、anchor、origin和稳定排序的三份实际文档获取 SHARE，复用原 S17/S18/S19/S20 查询校验真实原文、Ed25519、出处/部署/root/期限及原 Source/account/basis。公钥和 root revision 来自实际 permit/登记快照，调用者不能提供文档、公钥或 PASS。末复核已持锁原 proposal/event/Source窗口和 authentication hints；hints仍不具备JWT认证权。

原生产模块36,887字节完整保留，SHA de6b574718c9729b49d5314fa1a5f334dd08c8d33ef327872820bd531cd5637c。原测试除六个新案例登记名外原内容完整保留。精确当前文件和全部日志SHA见同名JSON。

## 实际验证

- RED-r1执行准备stdin编码失败，exit5/无案例，不能作为业务RED；RED-r2真实原登记/原SCRAM先通过，新常量缺失1FAIL。
- green-r1/r2分别暴露批准版本、account/basis版本bigint=text；r3暴露本次局部checked_at与原查询同名列冲突。仅固定参数类型和局部变量最小修复。r4三个实际正向PASS32.33s。
- expanded-r1 16PASS/8FAIL226.85s：三负例错误字符串版本、两不可变行注入被原保护拦住、三个竞争查询text版本类型错误。修测试构造，不改业务规则。隔离管理事务LOCAL replica注入/精确恢复，业务caller始终origin。
- expanded-r2 **24PASS/264deselected/7既有warnings/noSKIP226.02s**。两个真实原API布局、9合法但错误exactrefs且requestHash重算、3已提交原registry漂移恢复、3普通角色拒绝、6新域原行真实pg_blocking_pids阻塞及actual callerCOMMIT释放。
- adjacent-r1 **232PASS/114deselected/7既有warnings/noSKIP1030.91s/exit0**，范围为原native/本次signed/current-signed/supplier/permit/window/epoch，三个实际文件：transaction_pg、source_pg、publication_epoch_locks_pg。不是全业务或未实现prepare全链验收。

终态只读回读 own retained aos_test_83e3dd94f7e0_ti4_test，cluster7693564235776004128、a0v_156；public.prepare_capacity_source不存在，本次临时command/signed函数0。fixture每次清理临时harness/functions并回验原checker。无正式库访问、库/卷/备份删除、正式服务重启或push。

AST、原内容保护、代码/方案whitespace和凭证扫描通过。失败原日志字节保留，日志尾空格不清洗，不宣称所有原日志whitespace干净。浏览器不适用（无UI/API部署）。代码与方案一致性复核完成；仍未执行正式安装和 Source 后续入口。

## 明确未完成

完整157 S01安装/目录审计、global account/Provider双向归属、pending prepare、受控signer原JWT与精确待签bytes、commit/actual Source callerCOMMIT/current consumer以及final COMMIT TTL均仍需要真实实现及验收。临时owner harness不是正式接口，当前读根/批准期限不是final COMMIT TTL证明。无SourceDelivery、无真实Provider开启、无自然首链或发布通过。下一沿本plan完整157包继续。
