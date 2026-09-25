# W5ca2｜旧托管器自动重启门禁 STOP

1. 复习 231、230 L0、W5ca1 文件路径诊断与精确租约。
2. 方案先提交 `m1@0104e49e`，要求旧失败 label 无 PID 才可新启动。
3. 新鲜门禁发现旧 label 有 PID35932；立即停止新动作。其 stdout 后验有 20 条失败预检，W5ca1“单次 submit”非进程单次。
4. 精确移除旧失败 label，读回无 label/PID/wrapper/18181/8080 listener；没有 W5ca2 新 `check` 或新 submit。
5. 本波无代码、无线上 HTTP 专项；W5c9y 29 passed/2 子测试仍仅历史离线基线。
6. 不能凭预检失败推断每次都没有内部副作用；仅可证明未出现 API listener/业务请求/原 definition 调用。
7. 8080 业务浏览器与 18181 文档验收均离线。
8. W5ca1 自动重启补证、W5ca2 audit/verification 与 D-waves/AOS CAS/Prime 同步。
9. 下一波 W5ca3 先设计/静态验证显式 `KeepAlive=false` 的隔离托管配置和进程 PATH，再新鲜门禁单次启动；不使用 `launchctl submit`。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
