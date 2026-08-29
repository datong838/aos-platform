# P07 exact cached tunnel 失效驱逐验收

- 自然事实：P07 在 `2026-08-29T00:00:02.671566+00:00` 新建自然 run，约 60 秒后因 `OperationalError` 失败；DLQ 为稳定去敏分类，Shipment source/projection 为 `19/19`，未冒充本轮成功。
- 根因：缓存 DB 连接失效后，数据库重连通过原 SSH 本地转发等待 30 秒仍失败；本地端口可接受 TCP 的探针不能证明远端数据库会话可达。
- 修复：DB 建连失败后以 cache key + exact tunnel 对象 identity 驱逐调用方使用的隧道；并发 replacement 不关闭。本轮不重试、不延长 timeout、不重放 DLQ。
- 专项：JDBC runtime、Cron guard、P07 Shipment、P08 CustomerLite、live executor 共 `83 passed`；compileall 与 scoped diff check GREEN。
- 扩大回归：`1234 passed`，另暴露 Workshop 旧种子复合键错误和 author/release bundle 漂移；两项均不由本修复引入，已继续进入独立整改，未伪报累计 GREEN。
- 外部边界：未手工运行 P01～P12，未读取或写入源业务表，未修改真实业务数据，未执行 Provider、发布或外部效果。
