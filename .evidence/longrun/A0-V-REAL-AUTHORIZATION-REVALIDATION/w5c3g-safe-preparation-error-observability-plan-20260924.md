# W5c3g Prepare 失败安全观测方案（2026-09-24）

## 目的与边界

W5c3f `bdbfdcee` 已证明两次失败安装均正式退休，三资源在 create claim 前取消；只读 release admission/registration 全过，但通用 `PREPARATION_EXECUTION_FAILED` 未留下具体异常分类。唯一 Host PID15014 空载、九路/12 调度关闭。此波只改错误观测，不新建安装、不发 prepare/verify、不读商城源。

## 最小实现

1. 在 `services/aos-api/aos_api/extension_runtime/preparation_worker.py` 的 `PreparedJob._watch` 原始异常捕获点，以局部 helper 构造有限长度的异常链：仅 `type(error).__name__` 与 traceback 的**仓库内相对文件名、函数名、行号**；禁止 `str(error)`、args、locals、SQL、artifact、payload、身份字段。输出到原 Host 的私有日志；不写数据库/Receipt、不影响原 finalize/re-raise 语义。Error chain 缺 traceback 也只记录类型。
2. 新增定向测试证明敏感错误消息完全不进入日志、链长度/帧数有界，既有 prepare 失败及资源清理测试仍通过。
3. 只在 operation 未终态数0、三个失败安装均 uninstalled、Host 空载、九路/12 调度/canary不变时，定向重载唯一 launchd Host 一次，读回新 PID ACTIVE 空 liveTargets 和 Docker PATH；不创建第二 Host。
4. verification、m1 commit；下一波才新建全新 predecessor-free installation。若仍可只读定位更具体的根因，先做诊断/修复，再批准新安装。

## 停止条件

日志意外包含错误值/秘密、Host 重载无法唯一、运行 operation/资源未闭合、测试改变原失败语义，冻结，不推进下一次 prepare。
