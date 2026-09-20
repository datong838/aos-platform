# BM 信任根轮换与四包补丁版本恢复验证（2026-09-20）

## 结论

`BM_REGISTRY_ROTATION_GREEN`，且独立只读复核为 `BM_REGISTRY_ROTATION_OBSERVED`。

本波恢复了新的持久 Ed25519 信任根，并以不可变新坐标正式发布四个经过隔离构建与 qualification 的包。没有覆盖或重签历史版本，没有创建 BM 安装，没有读取商城源数据，没有调用 Provider，没有启动 Runtime Host、worker、cron 或 18181 服务。

## 1. 基线与方案一致性

- 起始 HEAD：`6139cc5ee61fb8d506f109503d288403b14a33c5`（BM material recovery gate 已冻结）。
- 方案文件：`bm-trust-root-rotation-plan-20260920.md`。
- 新增实现：`scripts/a0v_bm_trust_root_rotation.py`。
- 新增测试：`services/aos-api/tests/extension_runtime/test_a0v_bm_trust_root_rotation.py`。
- 所有构建、签名、私钥、信任根、数据库备份与结果文件均位于仓库外：
  `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260920/state/q-advisor-baseline/bm-trust-root-rotation`。
- `.env` 未修改；旧发布坐标、BL 历史与当前安装未改写。

## 2. Preflight 与候选准备

- `PREFLIGHT_GREEN`：18181 未监听；目标新坐标初始计数为 0；安装总数 73、正租户 73、canary 0。
- 四份仓库候选输入均为无签名、无 runtime image index 的构建输入；复制到仓库外后仅做精确补丁版本 token 替换。
- external candidate preflight：4 bundles、3 runtime members、8 modules、15 runtime operations，结果 `PREFLIGHT_GREEN`。
- 新坐标：
  - `domain.ecommerce.core@1.4.1`
  - `platform.ecommerce.niushop@1.23.1`
  - `solution.ecommerce.growth@1.10.1`
  - `solution.ecommerce.operations-base@1.2.1`

## 3. 隔离构建与 qualification

- build outcome：`BUILD_GREEN`。
- output tree hash：`sha256:881663413adc8460835f568b3bfda0cc7e6ee05a4e7ec7fd84c4833c31e35a0d`。
- 固定 base config digest：`sha256:0505371492f8406a47d406e1d1ea3bcf707a95fc1ddf785bf6c95c84df55922a`。
- qualification outcome：`QUALIFICATION_GREEN`。
- 三个 runtime session 均为 exact registration、2048 heartbeat、released cleanup；core event 与 analyst workspace probe 都明确为 `qualification-fixture-only`、`executionAllowed=false`。
- `imageIndexBytes`、`imageDigest`、`dependencyLock`、`sbom`、`backend`、`schemaCompatibility`、`schemaRequirements` 七项篡改均被拒绝。
- build/qualification effects：registry publish、installation mutation、Provider invocation、external publication 均为 0。

## 4. 新信任根与正式发布

- key id：`a0v-local-ecommerce-recovery-v2`。
- trust root revision：`sha256:d2254e25330e449fe6cb5d76a9269609ecfaa6f49e53ec6e0b1a4287d31e8de6`。
- 私钥与 trust-root 文件权限为 `0600`；签名包逐个通过 `ReleasePolicy`。
- 发布前 PostgreSQL custom-format backup：
  - path：`.../backups/aos_meta_head-pre-bm-registry.dump`
  - size：`10980243` bytes。
- 四坐标均严格执行一次 `create -> validate -> publish`，随后逐项由 store 精确读回 `published` 与预期内容一致。
- 内容 hash：
  - core：`sha256:f573b97f786140668562ce8b07fb6ae86a8cb7027392a07a78fe6fbc68816524`
  - niushop：`sha256:fad1daa94833cfe7583f7ee7a54377c99c3c276423ed1d69ab4fd80383b2d912`
  - growth：`sha256:8c5570a5f5411b45b394c270423503ec1383d879cb0b66c484a86cd4a44ec8c3`
  - operations-base：`sha256:4dbf45fa63a5bf23082fb044f3c6eef6669f21f926f3748641fa115a2ef2bc3d`

## 5. 独立只读复核与无副作用边界

- registry version count：19 -> 23；target count：0 -> 4。
- installation count：73 -> 73；正租户 installation：73 -> 73；`dev-org/dev-project` canary：0 -> 0。
- observe：四坐标均为 `published`，签名内容 hash 与 build receipt 一致。
- 18181 未监听；本波没有 Runtime Host、snapshot worker、cron 或自然 attempt。
- `sourceReadCount=0`、`providerInvocationCount=0`、`installationMutationCount=0`、`externalPublicationCount=0`。
- 230 L0 继续挂起。

## 6. 测试、风险与下一波

- `python3 -m py_compile scripts/a0v_bm_trust_root_rotation.py`：通过。
- `pytest -q services/aos-api/tests/extension_runtime/test_a0v_bm_trust_root_rotation.py`：`3 passed`。
- 初测发现 builder 链作为模块加载时缺脚本目录导入路径；已在新执行器内部做临时、可回收的路径注入，并复测通过。
- 发布前发现数据库容器用户为 `aos_app` 而非默认 `postgres`；备份逻辑改为从容器配置精确读取 `POSTGRES_USER` 后才执行，避免错误猜测。
- 仍有 7 条既有 Pydantic/Starlette warning，不影响本波结果。

下一波自动进入：**BM 运行时凭据恢复 + direct successor 激活**。先落盘下一波 plan；恢复专用 runtime-host identities 与角色，通过新 trust root / signed root 构造安装输入，保持 definition disabled、attempt=0，并在任何 host/worker 启动前完成纯 HTTP 18181 先行与第二 Runtime Host=0 读回证明。
