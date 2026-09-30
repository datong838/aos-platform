# W5CB4 BG00dz｜签名 BI Plan 未知结果原安装绑定文件级方案

## 上位合同与现状

已复习 231-3 安装状态机与强 ETag、231-9 栖月汇首链/重复副作用约束、栖月汇生意探究产品方案，以及 BG00dy。现有 `prepare()` 在一个事务里锁当前安装、核权限/签名/六实例、写 Plan+Receipt；`request_hash` 覆盖 body 与安装 ID/ETag/templateRef/actor，但哈希不能从只读 Receipt 反推出原安装。通用 `_replay()` 仅比较 request_hash、返回 Plan ref；如果实例状态在未知结果后变化，POST 预检会先拒绝，故正确恢复是同一键只读对账，不是再发 POST。旧 Receipt 的 `result_ref` 没有原安装信息。

## 最小选择

现有 Receipt 的 `result_ref` 是 JSONB object，允许新 BI operation 在原 Plan ref 的顶层精确附加 `installationBinding`（installationId、installationEtag、templateRef、actor）。保持 `resourceType/resourceId/revision/contentHash` 不变，通用 `_replay()` 仍按原字段读；仅 BI operation 受影响。写入前验证上下文是精确 UUID/正 ETag/模板 exact ref/当前 actor，防止产生貌似可信的部分绑定。BG00dy 只读 reader 兼容新旧形状，但本波仍返回 `installationBindingVerified=false`；原安装绑定读回合同及前端 SDK 留给下一精确范围波，一起做 RED/回归。**存储绑定不代表当前安装/权限仍有效，更不授权重发或启动 Host。**

不增 SQL 列、不迁移当前库、不回填旧 Receipt。若 JSONB 增量会破坏既有合同或无法独立验证，则停止此实现并另立备份、克隆全链与零执行迁移波。

## RED 与验收

1. `services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py` 增加新 Receipt 精确原安装绑定和旧 Receipt false 测试；对错误 actor/ID/ETag/templateRef 拒绝，Plan+Receipt 仍同事务，重复键不产生第二条。先 RED。
2. `aip_production_contract_store.py` 仅在 BI operation 构造存储形状与只读兼容提取；`ecommerce_business_investigation_aip_authority.py` 若现有上下文足够，则不改。
3. 本波不开放 UI 写入口。当前正式 OIDC/签名安装/六 active 实例/Host Owner 未齐，当前真库只读，Runtime Host/worker/Provider 关闭；browser-pilot 可用时才做页面截图。
4. 后端专项+W2 Store/API 回归、OpenAPI 合同、方案/代码复审、verification 与 D-wave，再精确提交/authority 投影。新响应合同与前端 SDK 在下一波一起升级。
