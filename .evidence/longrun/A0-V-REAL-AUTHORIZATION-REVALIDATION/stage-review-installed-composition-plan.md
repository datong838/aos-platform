# 阶段评审当前已安装运行时组合方案

日期：2026-09-12

基线：`b61f247f`

## 合同

1. `CurrentInstalledPackageInvoker` 暴露只限可信 `HostTransaction` 的 current snapshot reader；普通调用仍
   保持前后两笔独立读取包围一次 IPC。
2. `AsyncAnalystStageReviewCommandService` 可选接收同步 installed snapshot reader。新发布 prepare 时把
   `installedRuntime` 与原业务 authority 一起封印；commit 事务内重读并 exact 比较后才发布。
3. replay fast path 保持零 proof、零 runtime snapshot、零 IPC，按历史 Receipt exact 回读。
4. 新增 `build_current_installed_analyst_stage_review_service`，只用 concrete
   `CurrentInstalledPackageInvoker` 组装，不接受调用者自报 runtime snapshot。
5. 不公开 HTTP 路由，不修改安装、Registry、binding 或租户数据。旧 1.4.0 缺第五门继续由 session
   declaration 拒绝。

## 文件与验收

- 修改 `services/aos-api/aos_api/extension_runtime/installed_package_invoker.py`。
- 修改 `services/aos-api/aos_api/ecommerce_analyst_stage_review_async_service.py`。
- 扩充对应 invoker/service 测试。
- 新增本波 files/verification，更新 closure manifest。

验收正常五门发布、replay 零 runtime read、第五门后 runtime snapshot 漂移零发布、factory concrete wiring。
下一波评估受控内部命令入口和 1.5.0 candidate 构建/安装前置，不提前改变当前 1.4.0。
