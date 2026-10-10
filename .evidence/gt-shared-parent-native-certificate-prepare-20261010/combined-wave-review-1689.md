# 完整组合准备检查点复审

Rules：231、joint §11.3、原Task10/Task3精确E范围，m1单写。无产品代码变动，不push。

R23漏三个原fixture、R24第二随机planId违反原幂等、R25runtime schema权限负门异常期望过窄、R26原Judge deadline拒绝、R27组合通过但漏相邻source fixture。各失败新DB单独只读对账，不重放、删库、延期或放宽规则。修复均test-only，失败源/日志/结果保留；原日志仅本地留存、SHA绑定，不提交完整pytest局部值。

R28原完整node 1 passed/154.51s；原Source/JWT/审批/签名、samecaller四cert负门、Target原Input/Intent/plan/call/ledger幂等、Judge awaiting_target_result依赖、四表20DML42501、直接schema SET42501、固定test-only Owner约束组23514、实际COMMIT23514及原相邻Source40001全部保留。独立pg_xact_status实际组合aborted，各风险/证书/manifest为0；Root1仅实验bootstrap。

初次独立读回误将相邻Source已知COMMIT的guard metadata也预期为0，断言失败保留；r2逐项核同physicalAccount、xmin=writerxid、version2/committed与40001，保留合法metadata，不称metadata为准入。12产品及实验helper当前sha一致，ModelIssuer无C直接EXECUTE。

完整R27保留目录READ ONLY：26源码候选event匹配49trigger（35即时RI+7原deferredguard），7guard含同名require_joint_finalization两表，未SET/DDL；目录不是实际队列或完整event fixedpoint。实验Owner固定入口只负验证，不是产品finalizer。

不同次运行速度波动，去额外trace后仍154s含后续相邻；不能宣称性能稳定或deadline开销单因果。仍无真实Target模型结果/Judge结果与Usage、合法joint finalizer/正式可信Root谱系、实际经营首链。Task9/10及原Goal维持ACTIVE，不写完整Delivery。UI未改，本波浏览器不适用。

下一已登记安全步：完整四表native目录/FK/trigger body闭包对账（35RI与新增调用边），精确冻结所有效果再设计同名组收敛，不能用SET ALL解除guard。第二候选实际Target结果到Judge producer需正式结果/合同，不伪造。
