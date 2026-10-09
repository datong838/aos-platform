# Source 到期后实际 COMMIT 观察与独立核验

使用 Rules：用户 AGENTS.md、aos-engineering-delivery、231、原 Source 最终提交合同、m1 单写与未知结果先只读对账。仅改本证据目录的诊断与独立核验文件，产品及原 fixture 均未修改。

真实 shared 布局原事务 xid13812/pid27985：finalize 02:53:01.302384 UTC，原 Source valid_until 02:57:57.635277，实际 COMMIT 前 02:57:57.741280、后 02:57:57.760993；真实签发 JWT 03:04:40 才到期。未改 Source、审批或 basis 期限，没有时钟 mock，COMMIT 仅一次。独立保留库读回 xid committed、精确 Source 哈希与原生 C 签名、finalized 和原事务 provenance 一致。

完整 pytest 退出1，322.77秒：主体1 PASS，teardown1 ERROR。清理已撤销临时接口后，原 fixture 重查已过期的签发输入，固定拒绝异常与原断言期望 false 不匹配。不能把该轮称为全部通过。独立读回两角色 NOLOGIN、三个临时接口不存在、原产品文件哈希未变、原31资源身份/启动/卷/端口未变；独立核验通过不覆盖测试错误。原 verify-r1 与原日志保留；不重放事务。

本 Task 仅交付实际期限跨越及提交结果观察；不决定最终 COMMIT 时间语义、不批准完整 Source/epoch/legacy 功能、不授予执行权限，也不证明自然首链。独立模型 review 入口仍为此前 daemon 局部失败，不虚称通过。下一已登记候选为消费者当前到期禁入和 distinct 布局观察；先调查消费者入口及完整认证依赖，后按文件级合同验证。当前正式库、服务、Host/worker/Provider 和 Goal 状态不变。
