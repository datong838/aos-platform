# BM 信任根轮换与四包补丁版本恢复计划（2026-09-20）

## 1. 现场与目标

- 基线：`m1@6139cc5e`，BL 已正式退休；BM 因历史签名私钥、信任根与签名包目录缺失而冻结，尚未创建 BM 安装。
- 重启后 Docker 临时镜像缓存为空；该缓存不是发布材料的持久权威，不能据其缺失重签历史版本。
- 仓库仍保存四份受版本控制的候选输入，现有隔离构建器会在仓库外补齐依赖锁、SBOM、schema 证据与 OCI image index，并执行签名篡改负向测试和真实隔离 runtime session qualification。
- 本波只恢复 registry 可用的不可变新坐标：
  - `domain.ecommerce.core@1.4.1`
  - `platform.ecommerce.niushop@1.23.1`
  - `solution.ecommerce.growth@1.10.1`
  - `solution.ecommerce.operations-base@1.2.1`
- 历史发布坐标、安装、route、definition、runtime host、商城源数据均不修改。

## 2. 边界

- 正租户仅做 registry 计数与安装计数读回；`dev-org/dev-project` 只允许零 canary 断言。
- 不读取商城源数据；230 L0 保持挂起；不调用 Provider；不手工 `run_definition`；不启动 cron、snapshot worker 或 Runtime Host。
- 新私钥、信任根、构建树、qualification journal、数据库备份与每步结果只写仓库外 `.aos-recovery-20260920/state/q-advisor-baseline/bm-trust-root-rotation`，敏感文件 `0600`、目录 `0700`。
- 不修改 `.env`。后续 BM 激活必须显式引用本波新信任根和签名包根，不能隐式接管现有服务配置。
- 任何未知提交边界均停止写入：先按四个精确坐标读回状态；只有 `not found`、`draft`、`validated`、`published` 的单调状态允许继续相应的下一状态转换；内容不一致立即冻结，禁止覆盖或重发。

## 3. 串行步骤与完成条件

1. **preflight**：固定 git HEAD、候选源树、四个新坐标不存在或与本波内容精确一致；读回安装总数、正租户数、零 canary；确认没有 18181 listener、AOS host/worker/cron 进程。
2. **prepare**：在仓库外复制四个候选输入，以严格 UTF-8 token 替换形成补丁坐标；断言旧 token 全部消失、新 manifest 坐标精确、源目录无 signature/runtime image index。
3. **build**：复用 event-complete builder，动态固定 external candidate root、四个新坐标、15 个 runtime operation；在 `colima-aos-extension` 隔离引擎构建三镜像并产出 immutable build receipt。
4. **qualify**：复用同一 builder 执行三份真实隔离 runtime session、2048 次 heartbeat、core event fixture probe、资源释放、签名篡改拒绝；qualification receipt 必须与 build receipt 和当前 HEAD 一致。
5. **sign/publish**：生成新的 Ed25519 私钥与单一新信任根；签名四包并由 `ReleasePolicy` 复核；先完成 PostgreSQL 备份，再依次 `create -> validate -> publish`，每步使用独立幂等边界并即时精确读回。历史版本与安装计数不变，新增版本数恰为 4，canary 为 0。
6. **verify/commit**：执行单测、脚本 preflight/observe、敏感权限、进程与端口、DB/registry/安装零副作用复核；落盘 verification 后只提交本波明确文件。下一波自动进入“运行时凭据恢复 + BM direct successor 激活”。

## 4. 退出与停止条件

- 候选 token 替换不完整、manifest/runtime registration 漂移、隔离引擎或固定 base image 不可用、qualification 非 GREEN、数据库备份失败、签名或 ReleasePolicy 失败：本波停止写入并以精确 reason code 冻结。
- 任一 registry 坐标存在但内容、签名、publisher 或状态不符合预期：视为未知提交边界；只读对账，不覆盖、不删除、不重发。
- 发布后安装数、正租户数、canary、旧版本数任一变化：立即停止，不创建 BM。
- 本波不以 BM 安装或业务 attempt 为完成条件；只有四个新坐标正式 published、证据落盘并 commit 才算完成。
