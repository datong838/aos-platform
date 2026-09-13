# 异步目标分发方案

基线f808a7df，父任务Host/tests范围。installed package调用是异步，现有同步dispatcher不能直接承接。

修改 services/aos-api/aos_api/automation_dispatcher.py，新增独立异步入口，强制显式store和ClaimTarget，不使用默认数据库连接。领取前读取时间，等待结束后重新读取时间记录Receipt，避免慢调用沿用领取时间越过租约。异常只标needs_attention，无内部重试；取消传播，保留claim供现有过期对账，不再发送。

新增 services/aos-api/tests/extension_runtime/test_automation_async_dispatcher.py，验证精确target、最新时间、空队列、异常/空回执、取消和Receipt落库失败不重发。旧同步接口不改。测试为编排替身，不证明真实安装或分析业务。后继仍需真实分析处理器与当前权限复核。无主库修改/重启/push。
