# S20 permit 与独立 Source 签发根前置检查点

基线 m1@4e02ffc28586edc340f4f087f1a69a2f5222216c / AOS-001436。原Source Task保持ACTIVE，本记录不是SourceDelivery。

- RED：真实原批准Source/SCRAM及三文档签名登记后缺新常量，1FAIL/12.70s。
- green-r1：7个初始化ERROR，隔离PG64MiB共享内存申请32MiB失败，随后backend SIGSEGV和自动恢复；尚未执行新组合检查，不计业务拒绝。
- green-r2：首次remount失败却启动了测试，显式SIGINT130终止；保留日志，不计验收。namespace/remount初次缺PID namespace和显式tmpfs源，修正后同容器实际shm256MiB。未重建/删除数据库或数据卷，没有正式库操作。
- green-r3：7PASS/55.00s。原permit文档S17独立验签通过，错误policy exacthash、Source signer publisher/key/revision/publickey、不足Source覆盖窗口被新组合拒绝。
- root-r1：10PASS/76.88s（包含上述七项）。新增真实snapshot内单独Source root expired/future/revoked，policy/permit所用签名根仍有效，S17文档通过，新组合拒绝。
- 最终相邻累计：72PASS/122deselected/7既有warnings/noSKIP/351.67s。含新10项、原supplier/window/S17 current-signed与原epoch/withdrawal锁；未重跑全Source入口五项known42883，不宣称本轮全入口通过。

实现仅向publication_store追加55行4415bytes，完整原前缀SHA256 03ac379d62f253b81459771ad78bde2464515976a7d5d29d96ff26a3ad4671a9不变。fixture两可选故障参数默认为None，旧正常行为不变。S17 policy/permit复用原真实注册签名/当前部署/registry SHARE fence，exactpolicy引用、publisher/key和同origin/snapshot/epoch组合；Source signer在同immutable snapshot按精确Unicode codepoints定位，重解析整个原root snapshot后核全部实际root字段/canonical，revision/key一致和末时点不撤销，所有bootstrap/文档/签名根末窗口重核，原批准Source窗口在permit内。返回原Source/permit与实际root key，无发行权限。

方案/代码复审：未复制Python验签判定、未信verified标志、未改变旧角色权限/旧查询/旧数据；permit文档签名根与授权Source根独立。原依赖锁前缀、S19最终审批窗口和未来157完整调用仍强制，CTE顺序不作为锁序证明。纯未安装SQL，浏览器N/A。diff--check通过；测试handles已terminal，无并行写者。

恢复对账：同容器ID/StartedAt/全部mounts，集群7693564235776004128、a0v156；旧保留aos_test_7dd91a1512de_ti4_test三文档重新整hash+Ed25519校验通过，public.prepare仍不存在。HostConfig仍64MiB，实际256MiB仅临时remount，容器重建后的持久配置需另行安全门；backend崩溃内因未超出日志证据断言。保留全部库/卷/故障记录。

尚未完成：完整157 prepare→受控sign→commit→实际callerCOMMIT→consumer，最终COMMIT TTL、完整SQL绕过/ACL/撤回/unknown，SourceDelivery、自然首链/八工作台/连续观察/发布。下一按原S01–S20逐项装配到完整157入口，不用更多孤立helper替代垂直完成。
