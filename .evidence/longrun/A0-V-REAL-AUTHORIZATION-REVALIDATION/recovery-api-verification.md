# 产品恢复API验证

2026-09-11，基线e0bea9f5，A0V-RECOVERY-API-20260911。

新增POST /v1/schedules/{schedule_id}/runs/{run_id}/recover；body仅claimId UUID且forbid extra，scope从Principal取得；沿已有数据写角色admin/developer/data-owner，其他403。不经内存schedule授权或回写，由持久调度/claim核验当前绑定。重复沿duplicate返回，缺schedule404、合同冲突409、未知错误503固定提示；不输出内部异常或假成功。

新HTTP测试添加路由前7失败1通过（路由缺失404）；最终26专项通过，含9 HTTP+17调度。验证可信scope/原run传递、角色拒绝不调用、UUID/额外tenant字段拒绝、固定安全错误及duplicate非新成功。HTTP使用轻量FastAPI加真实登录依赖覆盖替身、scheduler Mock；PG权限/claim事务另有证据，不是完整生产认证或真实恢复验收。diff-check通过；既有pytest退出JDBC日志问题未修。

public未迁移、API未重载。下一波运行历史恢复资格/状态展示与前端入口，然后隔离安装升级及实际栖月汇业务验收。真实首链和八工作台未完成，不push，230 L0挂起。
