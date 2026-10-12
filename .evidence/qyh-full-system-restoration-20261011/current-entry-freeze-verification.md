# 恢复入口冻结检查验收

实际RED：仅恢复入口新提交、API/旧preview不变时旧候选仍被接受；1failed。最小修复将被启动解释器导入的恢复入口加入原git blob对比，沿用已有manifest/文件权限/源码全量hash/分支/旧preview开关检查，无重复验证器或新权限。

专项及相邻70passed、0skip、7既有warnings（5.94s）。原正式OIDC先拒绝/只读HTTP/WS/tenant/schema检查均保持；未知结果未重放，真库与服务未改。方案/代码复核一致；本子步不能关闭parent全恢复Task。提交后须使用原冻结器生成最新候选并实际消费，私有源码不提交。
