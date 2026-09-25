# W5c7b 可信 Fleet Universe 合同设计方案（2026-09-25）

上位 W5c5h/W5c7a：Host lease/fence 代码仅隔离 PG/默认 off，真实 `aos_meta_head=a0v_092`；本机及已知会话 0 不能证明其他机器、离线 Host 或未来重启被排除。正式 stalled closure 须另行证明物理第二 Host=0、全机器范围、Fresh Owner 事务及唯一 key；24 小时到线仅为时间资格。

## 文件级九步

1. 复习 231/231-9、W5c5h/W5c6m/W5c7a、`a0v_093/094`、Host opt-in/worker fence 与正式 closure gate。
2. 本方案先提交；本波仅新增 `w5c7b-trusted-fleet-universe-contract-20260925.md` 设计证据及 verification，不改生产/DB/部署/Host。
3. 写出 fleet universe 的可信来源合同：唯一受管部署控制平面、列举所有启动面/机器/身份与配置版本的签名清单、不可变 revision/有效期、覆盖性声明；未知/未受管/离线节点不能被“零观测”抹掉。
4. 写出阻断旧 Host 重新进入的顺序：迁移与全路径 fence 先验收、旧 Host 停机/credential 或部署入口撤权、每节点 shutdown ACK 与控制面禁止重启、跨机进程/容器/DB 连接读回；缺任何一项即 fail closed。
5. 受限 Host topology/closure/lease 测试与 W5c5k–z/W5c6a–z/JDBC 累计回归；设计不是测试绿色的替代。
6. 浏览器只读 rev4 停用，不保存/运行/冲刷队列。
7. 方案/代码一致性复审：标记已实现/仅设计/未部署，明确 Fresh Owner 单事务与独立 closure plan/key 的另门；不能把新设计当现网授权。
8. verification 后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立记忆并读回。
9. 下一波 W5c7c：先方案，选一个可独立实现的 fail-closed 纯合同/验证器切片；真实迁移与 closure 仍禁入。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
