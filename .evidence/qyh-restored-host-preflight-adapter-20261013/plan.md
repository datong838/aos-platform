# 栖月汇当前库运行准备预检适配

Rules：231 原安装状态机、aos-engineering-delivery，先方案后 RED 和最小实现；唯一 m1 写者；原签名读取、租户隔离及三平面非 Owner 身份检查；本轮仅只读预检，不启用 Host/worker/Provider，不提交业务操作，不改库、原卷或已有正常历史路径。

本轮文件：`scripts/a0v_current_runtime_host_preflight.py`、`services/aos-api/tests/extension_runtime/test_a0v_current_runtime_host_preflight.py`，以及本 Task 证据目录。父任务已登记两个候选：当前恢复库准备预检适配、独立 Source 权限演练；选择前者，依赖已批准恢复方案和原受保护身份文件，真实启动仍需正式门。原生产 control_wiring 接线留下一独立步骤，不能把本适配测试通过当运行就绪。

问题：原 Host 预检委托固定旧预览库/安装；当前 aos_meta_head 中栖月汇恢复安装为 approved revision3。已有 select_current_installation 实际只读核验当前物理库/卷、精确安装锁及四包签名成功。已激活 image reader 不能用于尚未 apply 的准备门。

实现：抽取现有三平面身份/当前库/Host 分配/配置候选/身份文件代际复核为共享内部函数，历史 preflight 原样委托；新增明确 preparation-only 的恢复入口，调用现有恢复 select_current_installation，取得既有受保护 API 参数和可信签名根，然后进入同一个身份门。不复制 release、authority 或 role 验证，不借此放宽 FULL 模式。CLI 两种输入严格互斥、禁止残缺恢复参数回落历史路径，恢复模式必须显式 --preparation-only；所有文件路径为绝对路径。

RED/验证：新增恢复模式禁止 FULL、缺参/非法路径、原 select 返回不合法范围/授权拒绝、真实 selector 委托参数、身份门共用和代际保护；原历史门测试累计回归。保留最初失败和终止状态；没有当前真实三平面凭证通过，不能宣称 live Host 预检 GREEN。新逻辑不触及 UI，浏览器不适用；当前八工作台仍未恢复。评审确认原历史输出保持、错误不外泄凭证、无新运行权限；下一步才以独立计划接入 control_wiring。
