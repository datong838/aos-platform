# W5CB4 BG00cu｜独立签发者单次决策组合文件级方案

## 上位方案与边界

复习 231-4 专用非 owner DB 连接、231-5 未知结果只读对账；BG00cn 普通 API 禁用默认签发，BG00cr 外部 JWT/tenant，BG00cq 精确 Event 只读查询，BG00ct 预落盘 at-most-once Receipt。当前 `aip_network_issuer_service.py` 只支持 Inquiry，DecisionCommand 被拒绝。该组合只供未来独立 OS 用户/私有 IPC 调用，本波不把当前 API 路由切过去，也不接当前库。

## 文件级计划

1. 在 `services/aos-api/tests/aip/test_aip_network_issuer_service.py` 先 RED：无正式认证时不落 attempt/不开连接；先 reserve 再最多调用一次 `decide_network_activation`；决定异常或读回 UNRESOLVED 时返回 UNKNOWN、不重发；同 key 再次调用被 attempt Receipt 拒绝；Event 精确 OBSERVED 才返回已观察，CONFLICT 拒绝。单元替身只测试顺序，隔离 PG 只读 Event0 用真实 issuer 权限证实 UNKNOWN。
2. 最小修改 `services/aos-api/aos_api/aip_network_issuer_service.py`：增加独立 `issue_decision_once` 函数。严格 Command、显式 `decision_connect_factory` 与 `read_connect_factory`、expected DB、私有持久目录；BG00cr 认证→BG00ct reserve→BG00cn 单次 `decide`→BG00cq Inquiry。调用者不能提供可信 actor；不记录 JWT；所有结果仅由精确 Event 读回判定。异常或查询失败归 UNKNOWN 并保留 attempt Receipt。
3. 不建立 Unix socket/HTTP 入口，不启真实 issuer；正式 OS 身份、私有目录及 HBA 与外部 IdP 仍另波。若没有当前第二 checker，正向 Event 不能冒充业务验收。
4. 专项/邻接、隔离克隆负例、方案/代码复审、verification、D-waves、m1 精确提交、authority/Prime 同步。
