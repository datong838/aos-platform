# 受控原批次日志与恢复适配验证

2026-09-12，基线cb346e4b。ControlledIngressJournal固定exact claimsOwner/scope/run/ref/actor，当前Control检查先于run锁；每次原始envelope/derived保存和running绑定均重新核对claim及当前图源。历史读取限定固定target，不导出执行许可。复用原Ingress/Derived/RecoveryClaim，不增加表、状态游标或另一套恢复算法。

缺模块RED后专项8 passed；补错actor回滚后，与当前claim、既有Ingress PG/恢复合计46 passed。实际PG证明同一空观察/派生准备幂等；原claim_failed_run可从stopped_failed原地恢复相同run和parentHash，重复claim返回false且源占用仍1；错误actor则run仍failed、recoveryClaim=0。每个写入阶段当前拒绝均不产生derived；固定scope/run不可替换。底层资产/签名/角色授权为明确fake，不能称真实批准验收。

AR2闭包1800/158/93五类错误空；diff check通过。主库仍023，024未部署；未读真实源、未启动P01。此模块只是恢复与持久化适配，不包含独立claim事务提交或首次源调用，不能凭构造实例放行读取。真实生产入口、过期审批的明确续期恢复与页面交互仍待接。

下一波：独立提交占用→重新当前校验→一次有界选列读取→保存原始批次；旧占用无批次为未知结果。继续核对转换逻辑必须使用已安装/已批准的映射，不能沿旧路径忽略钉住资产。m1单写，不push，230 L0挂起。
