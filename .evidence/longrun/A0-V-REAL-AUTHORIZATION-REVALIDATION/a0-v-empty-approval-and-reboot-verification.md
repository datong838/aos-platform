# A0-V 重启复核与空审批修复证据

基线 12e87ca7，m1，沿用 A0-V-REAL-AUTHORIZATION-REVALIDATION Lease。

原 aos-a0v-recovery-pg 容器恢复；没有重建卷、迁移或修改租户记录。只读审计见 a0-v-readiness-reboot-20260911.json：Provider 1，当前健康 0，route 0，active agent 0，provisioning 6，运行绑定 0，canary 0。首门 providerHealth，真实首链未完成。

模型路由方案撤销虚构单价、全能力文本路由和仅非空即能力通过的设计。真实价格来源、有效健康、模型评测和实际业务数据仍待完成。

显式空 allowed_approval_refs 原先通过 or 恢复 35-R1-C，导致禁用请求仍读取 Secret。新增测试先红：ForbiddenSecretResolver 被调用。修复为仅 None 使用默认后，探针及 A0-V 健康测试共 13 passed。默认旧授权和显式 A0-V 授权回归通过，空集合在 Secret/transport 前失败关闭。没有真实 Provider 调用。

存在既有 7 项 schema/deprecation 警告及测试退出后的 JDBC logger closed-stream 报错；测试退出码为 0，不将这些既有问题描述为已修复。

本修改只收紧显式空审批语义，不改变默认调用者和租户数据。无页面变更；未声称浏览器验收完成。下一步继续恢复诊断 API/web、核实价格来源、冻结精确模型评测，再推进运行绑定和真实首链；不 push，230 L0 挂起。
