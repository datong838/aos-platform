# W5CB4 BG00cs｜私有签发接口先接只读 Inquiry

## 依据与裁剪

复习 231-4 专用低权限连接、231-5 未知结果先对账，及 BG00cn/cr/cq。BG00cr JWT 门和 BG00cq 只读 Event 查询均已独立实现。真正 `decide` 经网络/进程失败后，仅查到 UNRESOLVED 仍不能证明首次尝试没有落库；当前没有持久 attempt Receipt，不能允许私有接口自动重发。因此本波先接无副作用 Inquiry 组合，签发命令在接口层显式禁入；把持久 attempt Receipt/一次性执行作为下一独立波。任务 Receipt 的原“bounded decide”交付在本波判为未完成，不把测试替身冒充进程验收。

## 文件级计划

1. 新增 `services/aos-api/tests/aip/test_aip_network_issuer_service.py` 先 RED：无正式身份不得开连接；只读连接必须来自显式工厂，按 BG00cq exact Event 查询返回；任何 `NetworkIssuerDecisionCommand` 一律 fail-closed，不能意外走 `decide_network_activation`；异常/UNRESOLVED 不重发。纯测试工厂只验证组合控制流，隔离 PG 读负例另测。
2. 新增 `services/aos-api/aos_api/aip_network_issuer_service.py`：接受严格 Inquiry、显式只读连接工厂和 expected database，先 BG00cr 认证，后借用 BG00cq 只读查询；不接受外部 request 自报的 expected actor，始终取签名 token 的 subject；连接只用 `read_only=True` 且不提供写入入口。签发命令入口直接抛 `ISSUER_ATTEMPT_RECEIPT_REQUIRED`。
3. 专项/邻接、隔离 clone 只读负例、代码与方案自洽复审、verification、D-waves、精确 m1 提交、上下文同步。

## 下波与禁入

BG00ct 先设计持久、原子、崩溃后可回读的 attempt Receipt 与单次签发执行；读写必须共用 exact tenant/proposal/key/hash、独立 OS issuer 与 DB 权限。之后才开私有 IPC/进程入口。当前库只读，不启 Host/worker/Provider，不发正式 Event，不碰商城源和旧 Run。
