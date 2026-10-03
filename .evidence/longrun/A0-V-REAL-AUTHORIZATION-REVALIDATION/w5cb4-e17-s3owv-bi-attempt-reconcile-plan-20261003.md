# s3o-w-v 第一切片｜BI 发行命令至原 Plan/Receipt 的至多一次桥

## 基线与上位约束

- 依据 231-3 原安装/Plan 同事务权限、231-9 原 AgentInstance 六身份、D-wave s3o-w-v 与 619。当前 HTTP 写口仍 `503 BI_FORMAL_ISSUER_REQUIRED`；本切片不接该路由，不写当前权威库。
- 原 `SignedBIPlanPreparationService.prepare` 和 `SignedBIPlanActiveRebindService.rebind` 接受安装 ETag、租户、OIDC Principal 与幂等键；原 Receipt Reader 用 actor+operation+key 只读查询，核 PlanRevision，但 `current_admission_verified=False`。写入可能已提交后连接断开，不能根据异常重发。
- 复用 `aip_network_issuer_attempt._reserve_attempt_receipt` 的私有目录 0700、标记文件 0600、O_EXCL/fsync 至多一次原语；按 BI 操作单独 namespace，标记只含命令无 bearer 的 hash 和重新验签 actor。此模块不得持有 DB 凭据，执行服务和只读 reader 由未来独立 issuer 进程显式注入。

## 文件级步骤

1. `services/aos-api/tests/aip/test_aip_bi_plan_issuer_service.py`：先 RED 验证每请求重验，首次持久 marker 后只调用一次原方法；重复同键仅回读 Receipt，错 hash/actor 返回冲突；原方法抛出可能已提交异常只读对账，不重发；查无或 reader 异常为 unresolved，不能宣称成功；错误目录在调用前禁入。测试双操作与严格 Receipt 安装/actor/版本匹配。测试双重对象仅证明编排，不作正式 DB 验收。
2. `services/aos-api/aos_api/aip_bi_plan_issuer_service.py`：最小独立函数，接受 s3o-w-u 严格命令、私有 attempt 目录、显式原服务和只读 Reader；执行一次后以原 actor scoped Receipt readback 决定 observed/unresolved/conflict；原始 bearer/异常不写日志或 Receipt；不自动重试，不返回“当前准入通过”。
3. 专项与相邻 619 命令/OIDC、原 BI store/readback、network attempt tests，编译和 diff 审查；必要时在可销毁原签名 full schema 克隆复查旧服务正反，不触碰当前库。验证文件与精确提交后更新 D-wave/620/Authority/Prime。

## 后续正式接线与风险

- 此切片仍无真正跨 UID IPC、独立 DB 登录/ACL、正式 IdP/签名六 Agent 来源。下一切片把本服务放入受限有限私有进程，使用内核 peer 和受保护凭据，克隆全链实测失败与恢复；当前 HTTP 不开放。
- 即使 Receipt observed，也只证明原事务产物与输入绑定，不证明当前安装/权限/预算/Host 可执行。正式当前库 migration 和切换需一致新备份、全 schema 克隆、回滚/恢复、零执行窗口。
