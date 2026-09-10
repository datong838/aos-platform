# A0-V 可运行电商 Candidate 制品资格验证

## 1. 结果

`A0V_RUNNABLE_ECOMMERCE_CANDIDATE_QUALIFICATION_GREEN`。

后续 runtime verify 复核发现，v3 尚未携带宿主强制的签名结构要求。该结论仍有效地证明 OCI admission 和组合解析，但 v3 已被 v4 结构兼容资格证据取代，不能作为 canonical 首装输入。

该标记仅证明四个版本化 Candidate 可以形成确定性 OCI、通过临时签名后的正式 ReleasePolicy 与 runtime admission，并可解析为预期组合。它不表示这些版本已经 canonical publish、安装、启用或获得真实业务执行权；A0-V 仍保持阻断，后续 publish/install 必须另立受控方案。

## 2. 实现与提交

- `4f8ffd61`：版本化 core 1.1.0、niushop 1.1.0、growth 1.4.0 的 runtime backend 与声明，并验证与作者态 exact tree 一致；operations-base 1.2.0 保持声明型。
- `6ff51f17`：新增默认只读 preflight 和显式隔离 OCI 构建器。
- `e03b1383`：新增临时签名、ReleasePolicy、runtime admission、组合解析及篡改拒绝资格模式。
- `ae395e4b`：修复临时 Registry 就绪竞争，使用并发 HTTP 服务及真实 `GET /v2/` 就绪探针。

改动路径：

- `bundles/candidates/ecommerce/domain.ecommerce.core/1.1.0`
- `bundles/candidates/ecommerce/platform.ecommerce.niushop/1.1.0`
- `bundles/candidates/ecommerce/solution.ecommerce.growth/1.4.0`
- `scripts/build_ecommerce_runtime_candidates.py`
- `services/aos-api/tests/extension_runtime/test_runnable_ecommerce_candidates.py`
- `services/aos-api/tests/extension_runtime/test_ecommerce_runtime_candidate_builder.py`

## 3. 最终构建证据

最终构建使用隔离 Docker context `colima-aos-extension`，平台为 `linux/arm64`，基础镜像 `python:3.11-alpine` 已存在本机缓存；构建使用 `--network=none --pull=false`。

| 项目 | 值 |
|---|---|
| 源提交 | `ae395e4bbdf898b703edf26fe4876d13f6cdc5a4` |
| 构建回执 SHA-256 | `894e9812c21a9fae455419b3219c8e30a85f957bc1a63450ef6655d34d717333` |
| staging tree | `sha256:dedfae13faa85c7a506f834aed50afb6d502b952df73796766df1fa37cd1f49e` |
| SDK tree | `sha256:3f3639b97991ccf571d6f062e6345525c307e4c30f45e62335bb6d73620cd63b` |
| dependency lock | `sha256:7082d71d73dfa0ef7a607045bfa22242621728e3346d99542087d6c629fbcacb` |

四包 content hash：

| Bundle | content hash |
|---|---|
| `domain.ecommerce.core@1.1.0` | `sha256:927174308b3353e0f2685f1423b515733de39b13e7878c5bdbbf93c9cf17dc93` |
| `platform.ecommerce.niushop@1.1.0` | `sha256:d20c3864ee8c2d10b6e4cf2ace8253857bd66d2a80742eb1bb0aeadc80bac49f` |
| `solution.ecommerce.growth@1.4.0` | `sha256:a3a1ab89e02b259316e4a52534429a2463ec8669d394b81372f011929a7b991e` |
| `solution.ecommerce.operations-base@1.2.0` | `sha256:eaf3a9ac9e0faca35246ed85d709ad97c8e1e8a4e5a7e315f1b4a0d6f896a298` |

三个 OCI identity：

| Runtime member | manifest digest | config digest |
|---|---|---|
| core | `sha256:4c40b49b1e1884750473e5945c8facec48610bb1882f592d9dee83689b3c9781` | `sha256:60be70024308005902d799a295d1d000f65333da3cab65c702b92dd13b7f188f` |
| niushop | `sha256:11781363f715f276f4744137f78650e22b25b7fd333e10434d6cb1a98b32c506` | `sha256:9c7f9fe391126b7c4028743a52c9779d4ce7ff754bbed470a6abd0617a284c70` |
| growth | `sha256:83a1aeaafdbf3982953f02b29b661230ec61c3553d6d70908ac1f2382b06a1b3` | `sha256:d532ab5fc519661d96b3c1893bc2b1bf9f9a1cfbf62935ee2a24742bb73d5555` |

上述所有摘要与较早成功试跑完全一致，证明重复构建结果稳定。最终资格回执 SHA-256 为 `44ce0a64eac924ce0616db7b53ec794387e6ec55eacd9e898efb242015a3f646`。

## 4. 准入与组合验证

- ReleasePolicy：四包均使用进程内一次性 Ed25519 私钥对临时副本签名，并通过当前信任根、五类 release evidence 与内容描述符校验。
- runtime admission：core、niushop、growth 均按 signed image index、dependency lock、SBOM、manifest digest、config digest 和本地 immutable cache 一致性通过。
- Composition：请求 niushop、growth、operations-base 后，resolver 精确加入 core 依赖；解析版本为 core 1.1.0、niushop 1.1.0、growth 1.4.0、operations-base 1.2.0。
- 清单：八个 Workshop module、三个 runtime member、12 条 registration operation。
- 篡改：`imageIndexBytes`、`imageDigest`、`dependencyLock`、`sbom`、`backend` 五类签名后修改均在进入 runtime 之前失败关闭。
- 临时签名副本在资格命令结束时删除；源码 Candidate 与外部 staging tree 均无 `bundle.signature.json`。

专项测试共 `52 passed`，覆盖候选源码、构建器、admission、M5 电商组合、release 安全、历史 release tree hash 与 successor 安全阻断。现有七条 Pydantic/Starlette warning 及进程退出阶段 JDBC 空缓存日志写入已关闭 stream 的 logging error 与本变更无关，不影响测试结论。

## 5. 故障与修正证据

1. 临时签名首次被正式验证拒绝。根因是 qualification helper 把 Base64 文本误传给要求原始 32 字节的 `TrustRoot.public_key`；改为原始公钥后通过。没有放宽验证合同。
2. 绑定 `e03b1383` 的两次构建在 exact pull 阶段分别返回 connection reset/EOF。根因是单线程临时 Registry 与只建立 TCP 连接的就绪探针存在请求竞争；改成 `ThreadingHTTPServer` 并以 `GET /v2/` 200 且正文 `{}` 为就绪条件后恢复。
3. 失败构建均返回 `SAFE_BLOCKED`、删除未完成输出并停止临时 Registry；未发布、未安装，也未尝试从网络拉取替代镜像。

## 6. 一致性与风险

实现满足资格方案的版本、构建、签名、admission、组合和无效果边界。构建回执记录的四类效果均为 0：Registry publish、Installation mutation、Provider invocation、external publication。

当前生成的签名仅用于资格验证，不能用于 canonical publish；正式发布仍需要 AOS 受控签名根、职责分离和 Registry lifecycle。镜像当前只存在于隔离引擎缓存，回执中的 loopback Registry 地址在构建完成后不可用，后续发布必须引用已记录的 manifest/config digest，不能依赖临时端口。
