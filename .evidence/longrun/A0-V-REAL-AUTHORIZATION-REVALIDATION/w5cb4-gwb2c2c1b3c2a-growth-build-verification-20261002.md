# GW-b-2c2c1b3c2a 验证：Growth 1.13 隔离构建与资格

2026-10-02 09:58 CST。基线 `aos-platform/m1 89feb64a`、Authority `AOS-001117`，Task `W5CB4-GWB2C2C1B3C2A-20261002`。方案 `w5cb4-gwb2c2c1b3c2a-growth-build-plan-20261002.md`。仅 `colima-aos-extension` 隔离 OCI 与仓外新目录；当前权威 DB/安装/Host/worker/Provider 不动。

| 步骤 | 本次输出 |
| --- | --- |
| RED | 新 profile 缺失：3 errors，退出1。补 profile 后原 `ReleasePolicy._assert_release_evidence` 拒绝首次构建，因为 1.13 源候选故意没有旧 1.12 的 `bundle-evals.json`；资格 Receipt 未生成。首次仓外 build 与 Receipt 留作反证，不覆写。 |
| 评测证据 | 对最终源码/构建 profile 跑六文件精确命令，`54 passed, 8 warnings in 5.20s`，退出0。将测试范围、源树 hash 与 `runtimeReadiness=blocked` 写入本波 `w5cb4-gwb2c2c1b3c2a-growth-113-bundle-evals.json`，SHA256 `ba6d5788…435f7`；不是模型效果或业务通过。profile 锁 hash 和来源，仅在 build 输出副本添加，已提交 1.13 源候选保持不变。 |
| 专项与静态 | 新 profile、旧 1.12 profile、新候选三文件：`9 passed, 7 warnings`，退出0；`py_compile`、`git diff --check` 退出0。原 profile preflight 四包、八模块、15 个总 operation，其中 Growth manifest 11 个 API + 14 静态贡献。 |
| Build r2 | `services/aos-api/.venv/bin/python scripts/build_ecommerce_growth_1_13_candidates.py --build --docker-context colima-aos-extension --registry-port 18438 --output-dir /Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-build-20261002-r2 --receipt /Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-build-receipt-20261002-r2.json` 退出0、`BUILD_GREEN`，输出树 `sha256:e46f9bd2cbc918e6ada1d96c364ba25a87e0e79c97fb0e5e8e8e60af4718ecaf`。Growth image `sha256:dc619ab1556fd16ec98d9985f8870373651c83cedb6bfd9d5c5ceeb1e9d59f53`，config `sha256:4483d2e202762ebde78f3b9fb622726c0cf6b04b77a7746b58c4b90b6cd44674`。 |
| Qualify r2 | 原 CLI `--qualify-output ...r2 --build-receipt ...r2 --docker-context colima-aos-extension --receipt ...qualification-receipt-20261002-r2.json` 退出0、`QUALIFICATION_GREEN`，同一 outputTreeHash；四包 resolved 版本 `1.4/1.23/1.13/1.2`，Growth 原 OCI `registration=exact`、25 贡献、2048 heartbeat、`cleanup=released`、probe 明示 `qualification-fixture-only`；七类 image index/digest、dependency lock、SBOM、backend、schema compatibility/requirements 篡改拒绝。 |
| 作用与清理 | 两份 r2 Receipt 的 registry publish、installation mutation、Provider invocation、external publication 全为0；隔离引擎 `docker ps` 无本波 active candidate container。旧 test-only 已退出容器保留，未删。1.13 源仍无 SBOM/eval/image index/签名；仅仓外 build 输出拥有新评测。 |

复审：上位 231-2 的镜像摘要、独立 profile、签名之前的资格门与本波一致；231-5 §9 的正式 accepted-stage 来源、八类当前配置、首登记 Owner 不由本波资格推定。第一次缺 eval 的失败暴露真实门槛，未通过复制历史报告或放宽 ReleasePolicy 绕过。下一切片：独立本地签名并核签名/OCI 精确摘要，同时区分正式当前信任根和测试签名，再审当前八配置/Owner。当前库 `a0v_118` 对代码 `a0v_135` 的最新全面重启仍未执行。
