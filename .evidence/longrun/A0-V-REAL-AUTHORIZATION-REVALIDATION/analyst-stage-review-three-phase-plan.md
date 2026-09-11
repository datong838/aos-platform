# 经营参谋阶段评审三段式协调方案

日期：2026-09-12

基线：`20909690`

状态：协调器实施完成，数据库 prepare/commit adapter 待办

## 合同

新增不可变 exchange/prepared 快照与异步 coordinator。prepare/commit 为显式异步宿主依赖，
runtime port 必须是 `InstalledGrowthStageReviewPort`。command、payload、expected 与 exchange 顺序
均绑定 canonical SHA-256；每次 IPC 前后复核，最后只调用 commit 一次。

prepare hash 错、IPC 拒绝/超时/取消/响应漂移、payload 被调用方修改、commit 失败全部停止，零重试。
coordinator 不访问数据库、不发布 Receipt；后续 commit 适配必须在新事务重读 current authority
snapshot 后才调用现有 Store。

## 文件

- 新增 `services/aos-api/aos_api/ecommerce_analyst_stage_review_coordinator.py`。
- 新增 `services/aos-api/tests/extension_runtime/test_analyst_stage_review_coordinator.py`。
- 新增 files/verification 并更新 closure manifest。

## 下一门

顺序、hash、变更检测、各阶段异常零重试、编译与 AR2-7 closure 全绿后提交。下一波实现数据库
prepare/commit adapter，并以 current snapshot 漂移时零发布为核心合同；1.5.0 仍 PENDING。
