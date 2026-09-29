# W5CB4 BG-00ao｜Eval writer 持久 Dataset/Suite 同事务绑定验证

按方案 `w5cb4-bg00ao-eval-writer-persisted-source-binding-plan-20260929.md`，只改 writer 预检和 test-only fixture/测试；当前库未写、无 migration/路由/Host。先新增“无持久 Dataset/Suite 应拒绝”的真签名独立登录测试；旧路径仍提交成功，`DID NOT RAISE EvalExecutionRejected`，RED `1 failed`、退出1。修改后 BG00aj writer 在同一 serializable 事务、Receipt INSERT 前精确读取 tenant Dataset/Suite：Dataset content/source/redaction policy/manifest/case 数、captured/created 时间；Suite Pydantic 解析及 canonical hash、target/dataset/judge、case 集、input/expected Artifact hash、gate threshold、创建次序均核 Report/Run。签名验证与 BG00ak 原子 INSERT 保持原序。

test-only `aos_bg00ad_schema_v2_20260929@a0v114` 的正向 fixture 改用 canonical Suite hash、有效 Dataset manifest、真 Ed25519 签名与独立非特权 writer；最小临时 RLS/ACL 仅给 Dataset/Suite SELECT，不给 INSERT/UPDATE。缺两表、单缺 Dataset、单缺 Suite、错误 Dataset/Suite hash、Suite case 不同均在 Receipt 前拒绝。聚焦 BG00ao/ak/aj `22 passed`，相邻含 unknown reconcile/签名/Report/迁移/预览累计 `75 passed`，退出0。`git diff --check` 和 Python `compileall` 退出0。

事后独立只读 SQL：test-only 与当前 `aos_current_preview_20260927@a0v114` 的 Dataset/Suite/Run/Receipt/Report/sidecar 六表逐表0；test-only 临时 policy0、禁用用户触发器0、BG00ak 临时 LOGIN0。API `/v1/health`、`/v1/ready`、Web `/aip/skill-publish` HTTP200，18181 监听0。当前正式 writer role/issuer/Owner/ACL/G2 内容/S3 仍缺，不构成业务首链。

复审限制：持久 Dataset/Suite 精确绑定只解决“Run 自报来源且两表空”的绕行。test-only manifest 的选择来源不是正式 G2 生产来源；Artifact snapshot 字节、脱敏 Receipt 签发/撤销、Judge/Target 执行器合法性、当前正式 Owner/批准仍需独立当前证据。下一波 BG-00ap 只读审查并最小补 Artifact source/redaction 当前性或判定正式来源合同缺口，不以这 75 个测试宣称 Skill 放行。
