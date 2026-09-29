# W5CB4 BG-00br｜NetworkPolicy 受控 Proposal Producer 方案

## 上位合同与当前事实

按 AGENTS.md、aos-engineering-delivery、231/231-5/231-9、41 网络方案、BG-00bi～bq 复习。AIP ActionStore 已持久化 Proposal/ApprovalEvent、幂等/CAS、风险底线；通用服务禁五固定系统 ID。当前真库 `aos_current_preview_20260927@a0v_115` 中 NetworkPolicy ObjectType/ActionType=0，正租户仅1条 owner 成员且无独立 checker；正式 active 仍422。本波只接待审 Producer，不接 checker、消费、策略 active 或 Host。

## 文件级施工

1. 先增 `services/aos-api/tests/aip/test_aip_network_policy_action_producer.py` RED：非 OIDC、缺当前成员/marking、缺或漂移元数据、head/版本/依赖漂移、跨租户与重复键负例；test-only PG 正向只产生 exact drafted Proposal、无 policy/head/revision/Receipt 写入，通用 decide 拒绝。
2. `services/aos-api/aos_api/aip_network_policy_action_producer.py`：定义唯一受控 `NetworkPolicyRevision` ObjectType 和 `aip_activate_network_policy` ActionType 快照规范；Producer 要求 OIDC、当前 tenant 成员 owner/admin 与 marking，锁定/读取精确元数据和当前 head，复用 BG-00bj target hash 与当前 Egress verifier，生成 R2 maker-checker Proposal。`approvalRef` 文本只在目标内容内，不当批准；Proposal expiry 由服务端限定。用同一租户事务和现有 AipActionStore/Receipt 机制，不新造审批表。
3. `services/aos-api/aos_api/aip_action_store.py`：固定策略 ID 在 Store 底层必须有精确专用 guard 才能 create；将 target binding hash 持久进 Proposal；在本波 checker 未接前任何固定策略 Proposal 的通用 decide 失败关闭。其他 Action 不变。
4. `services/aos-api/aos_api/routers/aip_runtime_guard_policies.py`：新增经 Principal 的 `POST /networks/activation-proposals`，只接 `Idempotency-Key`、`If-Match` 和严格候选；当前 dev token、缺正式元数据仍拒绝。该路由不发布策略、不手工运行。
5. 新建独立 test-only 全库克隆，基于已校验 a0v114 dump 恢复并升115或从当前只读一致 dump 克隆。仅 test-only 用表 owner 登记精确 ObjectType/ActionType 和合成成员/marking作为代码路径测试；所有成功标记为隔离代码证明，不能当正式账户或真实实例批准。当前真库全程只读；无新增迁移。专项/邻接、真实负向/端口、复审、verification、m1 精确提交、01/06/D-waves/authority。

## 风险与验收界限

AIP ActionStore 内部已有部分控制动作专用接线；不得放松现有 guard。新 Producer 必须在同一连接保存 Proposal，不能先看快照后另开事务写。无当前正式 OIDC maker/checker、受控元数据来源、独立 checker 与同事务一次性消费，本波不证明 active；若任何一项无法安全接线，先落精确 blocker 并转可独立主线。回滚仅撤新增 Producer 路由/guard，原五 active 422、数据库保留门和当前卷不变。
