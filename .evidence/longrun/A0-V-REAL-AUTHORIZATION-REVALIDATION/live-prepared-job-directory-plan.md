# Live PreparedJob 目录方案

日期：2026-09-12

基线：`78af8d63`

## 合同

新增进程所有的 `LivePreparedJobDirectory`，键固定为 TenantScope、installation id、generation。
只接受真实 `PreparedJob`，键全部从 job 自身 plan/tenant scope 派生；不接受请求方登记任意身份。
同键不同 owner 拒绝，同 job 重复登记幂等。resolve 必须提供 exact 三元组，未登记即拒绝。

`PreparationConsumer` 在完成 owner routing 校验后登记 job；关闭 consumer 时，无论 stop 成功或失败都
按对象身份撤销登记。登记失败必须先停止刚建立的 owner，不能泄漏 OCI 资源。目录不授予 Installation、
binding、epoch 或业务权限，也不持久化可重放 token。

## 文件与验收

- 新增 `services/aos-api/aos_api/extension_runtime/live_job_directory.py`。
- 修改 `services/aos-api/aos_api/extension_runtime/preparation_consumer.py`。
- 新增目录单测并扩充 consumer 隔离 PostgreSQL 测试。
- 新增本波 files/verification，更新 closure manifest。

验收 exact resolve、跨租户/错代际拒绝、重复 owner 冲突、consumer 登记/关闭撤销、登记失败清理。
下一波使用该目录构造当前 Installation/binding 前后快照 invoker；本波不接 stage-review service。
