# W5CB4 BG-00w｜隔离签名 Eval 执行证据纯验证

方案 `w5cb4-bg00w-eval-execution-receipt-verifier-plan-20260929.md`，基线 `aos-platform/m1@e32315a1`、authority `AOS-000871`。先复习 231/AIP-4/BG-00v，改动仅为两个 DTO、一个纯验签模块及隔离测试。没有迁移、当前库写入、真实 issuer 配置或生产 Runner 放行。

## RED → 最小实现

- 新合同测试首次收集 RED：`ImportError: cannot import name 'EvalExecutionReceipt'`，退出 1；补合同/纯验证后先得 `8 passed`。
- 复审发现已签 Judge Receipt 的 `outputHash` 可以与其 verdict 不符，新增隔离 RED 为 `Failed: DID NOT RAISE EvalExecutionRejected`，退出 1。现把 actual/expected/verdict/detail 的规范摘要与签名 `outputHash` 核对。
- AIP-4 Case 允许无 expected Artifact，先加读取 DTO 的 RED：`ValidationError: judge receipt requires exact result fields`，退出 1。现允许 Judge `expectedHash=null`，仍要求 actual/verdict/detail 且签名结果摘要精确。
- 证书按独立 `eval-execution` purpose 的 issuer root 验签，再按双 purpose executor 公钥验每 case Receipt。核租户、run/suite/case、exact Target/Judge ref、输入/输出/expected digest、发生时间、有效期、撤销快照、独立身份/公钥与稳定 Receipt ID；缺 root/撤销快照拒绝。签名 payload 有独立域标签，不读取或配置 OCI bundle trust root。返回 claim hash 供后继持久重放唯一键使用，不宣称本波已有持久 replay authority。

## 验证

- 新纯合同专项 `11 passed`。包含隔离临时 Ed25519 签名正向机制、同租户 exact 对、无 expected Case、租户/target/digest/receipt ID 偏移、缺根/撤销/错签/过期/跨 purpose 等负向。临时密钥只证明算法，不是正式 G2 签发证据。
- AIP-4 合同、Runner、E2、Skill 发布、Binding、安装目录相邻 7 文件 `58 passed, 1 xfailed`，退出 0。严格 xfail 仍为缺正式执行权威的旧 lambda 正向链。`compileall -q` 与 `git diff --check` 退出 0。
- 当前业务库 `BEGIN READ ONLY` 读回 `a0v_111`、栖月汇 Eval Run/Report `0/0`，退出 0。API/Host/worker/Provider 未因测试启动，18181 继续禁入。

## 边界

纯函数的 root 与撤销快照由调用方提供，本波未建立它们的**正式来源、完整性或持久事务读取**。没有 G2 内容 producer Owner、正式 Target/Judge issuer、执行 Receipt 持久表、跨进程幂等/撤销消费与 BG-00o 真实 S3 读回。生产 `AipEvalRunner` 的 Skill 拒绝未改，Gate/发布/Binding 均不能正向。持久 authority 和当前库迁移须后继独立波，先可恢复备份、克隆全链、零执行窗口；不读商城源、不重放旧 12 Run、不动 230 L0、不 push。
