# W5cab｜AOS-000725 前段风险逐条后继证据

方案 `m1@2b3b2253`。本波仅校准 `incomplete` 原索引 6–37；0–5、39–末尾与 13 条 hard boundaries 不动。删除 14 条已被后继证明、且真实根风险在其它项保留的旧状态；改写 2 条仍有真实风险但“24h pending”已假的描述。旧内容仍在 AOS 事件/Git 历史，不删除证据。

| 原索引 | 后继证据 | 当前保留边界 |
| --- | --- | --- |
| 删除 6–7 | W5c4x 隔离 Owner 拒绝门、W5c4y 12 Run fixture 成功/同 key 回放及回滚均已有 PG 验证。 | 4/55 原十二 Run 真实未关闭；W5ca5 Fleet/同事务真实授权缺口。 |
| 改写 8、11；删除 12–14、16 | W5c4z 非零 effect fixture/W5c5a 空输入 effect；W5c5d 注册 connector 只读握手；W5ca4 24h 已为 `ELIGIBLE_NO_AUTHORITY`。 | 8 真实原组 effect/closure 未证；10 非空业务数据未测；11 全机第二 Host/唯一真实 key/原子门未齐，15/55/56 保持。 |
| 删除 9 | W5c5a 原 group input + empty ingress effect 数已 PG 验证。 | 10 非空业务/derived/Dataset Receipt 未测。 |
| 删除 17、19、25–27 | W5c5i/j 093+默认关 lease 基础，W5c5q StoreAttempt opt-in，W5c5s 原 metadata 连接 current_user 角色探针；W5c6n 原 Attempt 17 skipped 在专用隔离 PG 显式跑成 17 passed。 | 18/20 真库仍 a0v_092/无真实 Host fence，21–24/28–35 下游分事务/Store effect 与默认关闭，55/56 全机排他缺。 |
| 删除 36–37 | W5c6e 已提供 Store effect 默认关的 Host lease API，并做新写/replay/失权/锁竞争隔离 PG；W5c5t/u 已给 Schedule/Recovery 根独立事务 opt-in 传播。 | 38 真实 Store API 未接线、真库无 094，35 跨独立提交 effect 和全机 Host 未证。 |

精确删除旧索引 `6,7,9,12,13,14,16,17,19,25,26,27,36,37`；只改写 8、11，原 55 项→41 项。未把离线代码/PG 结果当 live。W5c4u PermissionError throw site、老 12-source Schedule 未终态、非空 Store/全机 Fleet/历史行语义等仍留原风险。
