# A0-V 可运行电商 Candidate 制品资格方案

## 1. 发现的产品缺口

A0-V 的 active 安装缺口不能由旧 successor 脚本关闭。只读调查得到以下确定事实：

1. `solution.ecommerce.growth@1.3.0` 与 `solution.ecommerce.operations-base@1.1.0` release 是历史不可变快照，旧脚本 dry-run 已以 `RELEASE_SNAPSHOT_DRIFT` 安全阻断；不得把 AR2 新 backend 原地写入 1.3.0 release。
2. 下一版本 Candidate 已存在：`domain.ecommerce.core@1.1.0`、`solution.ecommerce.growth@1.4.0`、`solution.ecommerce.operations-base@1.2.0`。它们承载现行生产 Profile 等新增资产，但 domain/growth 尚未纳入 AR2 runtime backend 与 runtime 声明。
3. `platform.ecommerce.niushop` 当前只有持续演进的作者目录 `1.0.0`，没有下一版本 Candidate；作者目录已经包含 runtime backend，不能继续以历史 1.0.0 身份发布变化后的摘要。
4. 三个作者态 runtime manifest 均引用 `artifacts/runtime-image-index.json`，仓内没有该构建产物。AR2 物理生命周期测试运行的是测试期签名 fixture 与临时 OCI，不是可直接交给 A0-V canonical Registry 的版本化 Candidate 制品。

因此必须先形成可复现、可签名、可精确回读的最终 Candidate 构建输出，再讨论 publish/install。创建 active 数据行或复用历史 release 都会绕过真实缺口。

## 2. 本切片范围

### 2.1 版本化 Candidate

- 在既有 `domain.ecommerce.core@1.1.0` Candidate 中加入与当前作者态 exact tree 一致的 `backend/ecommerce_core` 与 runtime 声明；保留 Candidate 已新增 schema。
- 在既有 `solution.ecommerce.growth@1.4.0` Candidate 中加入与当前作者态 exact tree 一致的 `backend/ecommerce_growth` 与 runtime 声明；保留 Candidate 已有 production profile、模板与成本合同。
- 新建 `platform.ecommerce.niushop@1.1.0` Candidate，以当前作者目录为内容基线，将 manifest 版本提升为 1.1.0，并把 core 依赖下限提升为 1.1.0。
- `solution.ecommerce.operations-base@1.2.0` 保持声明型 Candidate；它不伪造 runtime backend，仍与前三项共同组成八模块组合。

Candidate 尚未 canonical publish，可以追加本版本实现；历史 `bundles/releases/**` 与已发布 1.3.0/1.1.0 摘要保持不变。

### 2.2 确定性构建器

新增 `scripts/build_ecommerce_runtime_candidates.py`，默认只做源树 preflight；只有显式 `--build` 才允许在指定隔离 Docker context 构建。构建器：

1. 固定读取上述四个 Candidate，校验版本、依赖、八模块唯一性和三个 runtime 注册清单；
2. 为三个 runtime member 分别构建 Linux OCI，镜像只包含对应 Candidate、AOS extension SDK、固定 runtime.json 和 runner；构建使用 `--network=none --pull=false`，不下载依赖；
3. 通过本机临时 loopback Registry 形成 OCI manifest digest，再按 digest 拉回同一隔离引擎，使 `RepoDigest + config digest` 同时可独立复核；
4. 在仓库外输出可签名的 Candidate staging tree，为各 runtime member 生成 `artifacts/runtime-image-index.json`、`artifacts/python-dependencies.lock` 与匹配 SBOM；不把本机 image digest 写回源码 Candidate；
5. 输出非敏感 build receipt，记录四个 bundle content hash、三个 manifest/config digest、平台、源提交和输出 tree hash；构建失败保留失败关闭结果，不发布、不安装。

## 3. 安全与权威边界

- 本切片不调用 Registry publish、Composition resolve、Installation create/submit/approve、runtime apply/verify/configure/enable，也不写 A0-V 数据库。
- 不连接真实数据源、不调用 Provider、不产生费用、不执行外部发布、生产/共享迁移或 230 L0。
- Docker 仅允许现有隔离 context；先验证 Linux、userns、seccomp。禁止隐式 pull、网络构建、宿主目录可写挂载和 privileged 能力。
- 临时 Registry 仅绑定 loopback；已拉回的 exact digest 镜像作为后续隔离资格验证输入，是否保留由 build receipt 明确记录。
- 不读取或输出签名私钥、Secret 或 credential。Candidate 构建输出保持 unsigned；签名与 canonical publish 属于后续单独阶段。

当前 A0-V 主 Task 不覆盖 `bundles/**` 与 `scripts/**`。修改前必须登记 `A0-V-RUNNABLE-ECOMMERCE-CANDIDATE-QUALIFICATION` 子 Task/Lease，由 m1 独占这些精确路径；完成后单独交付并释放。

## 4. 验证

1. Candidate 合同：四个版本和依赖精确，八模块 ID/route 无重复，三个 runtime backend tree 与对应作者态一致，registration operation 分别为 1/9/2 且初始 handler 失败关闭。
2. 历史不可变性：现有 release tree hash 专项继续通过，旧 successor dry-run 仍安全阻断，历史 release 无改动。
3. 构建安全：默认 preflight 不调用 Docker；显式 build 在隔离 context 完成，三个镜像均以 config digest 独立 inspect，平台/RepoDigest/无 Volume 条件满足 admission。
4. 制品 admission：对 staging tree 生成临时签名，仅在隔离测试内通过 `ReleasePolicy + admit_runtime_artifact`；篡改 index、lock、SBOM、backend 或 image digest 均拒绝。
5. 组合资格：Composition resolver 精确选择 core 1.1.0、niushop 1.1.0、operations-base 1.2.0、growth 1.4.0，并得到八模块、三个 runtime member、12 条 registration operation；不创建 Installation。

## 5. 退出条件

退出标记为 `A0V_RUNNABLE_ECOMMERCE_CANDIDATE_QUALIFICATION_GREEN`，要求源 Candidate、构建 receipt、实际 OCI digest、签名 admission 及组合解析全部一致。该标记只证明可发布制品具备资格，不表示已经 publish、安装、启用或 A0-V GREEN。

后续必须以本切片同一 build receipt/content hash 形成受控 publish/install 方案；若 A0-V 权威仍禁止安装写操作，则保持 blocker 并更新 authority，不能在当前切片越权执行。
