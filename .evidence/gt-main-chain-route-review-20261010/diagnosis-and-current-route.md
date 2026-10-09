# 主链路由复核失败对账及当前路由

基线3a1ddfc53493d4082ca6e24fc70e539b0a3f21d1/AOS-001667。新review Task独立仅证据范围、同唯一owner、工具禁用；冻结8原件/35971编码材料字节，原旧attempt未重发。新request-1667-r1入口真实exit1、stdout空、daemon generation898b4b6d失去注册归属；result-r1.json不存在，只有transport/log与ATTEMPTED_UNKNOWN。无verdict/PASS/消费，不认为auth401、不猜Provider计费/模型调用结果，不重发。

受支持只读CLI status --json返回两监听进程均current：1844（用户临时目录默认socket）、51811（/tmp/socket）。current是version/protocol/build元数据，不是会话功能证明。分别使用公开list --json --daemon-socket对两既有socket只读请求，均exit1/无stdout；1844返回generation318852be失去归属，51811返回generation898b4b6d失去归属。因此仅换socket不能恢复，不能从status current推定有可用review或无活跃任务。没有启动新daemon、关闭/杀进程、改注册项或全局设置。

本机源码定位（非所有历史进程代码证明）：CLI main.ts createDaemonClientConnection先连接/创建会话，成功后才能runPrintModeWithConnection；no-session不跳过daemon。aos_review.py子进程环境仅HOME/PATH，未携带TMPDIR，解释默认socket路径可能与用户环境不同，但两socket本次list均失败，不能把TMPDIR补齐称作修复。API/模型容量恢复策略不适用于这次本地daemon所有权错误；模型内部请求状态仍未由此次调查证明，不改attempt终态。

恢复涉及两个现有进程，无法读取活跃会话。已通过异步入口请求用户自行受支持恢复或授权受支持关闭重启；不擅自终止其他任务。不将此缺口放大为完整Goal blocked；现有原Task保持ACTIVE。六原Task在同owner/TaskLease逐字一致/noDelivery/noOverlap对账后通过官方renew延长至21:37:31UTC，不凭TTL删除、夺锁或变更base_revision。

当前首链路由（替代陈旧b66尾部作为直接施工入口；历史b56等证据不删）：
1. 继续已批准完整双父风险/actual occupation/joint方案；原完整两case四腿、两原parent10保留，所有普通/Eval/Judge共用guard和桶锁序，未知费用与未知transport义务不得清零。缺实际原来源时不能编造每腿金额、签名、provider结果或receipt；尚未实现真正joint finalizer/transport/Usage/Report/Gate。
2. 原v2Target private stored验证仅必要签名/hash/撤回/current identity/origin COMMITTED；测试字节producer不是实际Provider。真实rootbootstrap、joint receipt、transport来源仍需接入，之后沿原真实Target→晚绑定Judge输入→真实Usage成本→完整Report/Gate/current consumer推进，不以新增helper代替全链。
3. tokenizer来源仍局部缺口，原Model没有immutable tokenizer/envelope权威。不能把context/quota ceiling叫实际token、任意字符/字节算法叫Tokenizer；已批准隔离合同设计可继续，但不得调用未授权Provider取usage。
4. Source strict实际WAL/客户端确认截止裁决已异步请求，尚未答复；继续原严格要求和效果拒绝，不因经过时间自动改提交语义。原SQL/回调不能兑现该硬截止的反例不能删/退款/重放。
5. Prime恢复只解开独立review局部门，不授业务权；恢复后新冻结HEAD/hash/authority/Task审阅，旧attempt仅只读对账，成功返回也须消费当前绑定后方可记录，不自动执行建议。

业务原Goal完整范围保持安装/配置/禁入/恢复/卸载重装/自然首链/八工作台真实场景/连续观察/发布决定；这些没有被当前回归或资料审阅证明。无产品改动、无正式库/Provider/重启/商城/旧Run/手动run_definition/未知重发/push。此Task尚无独立模型结果、不写Delivery，失败对账与路由同步是本波结果。
