# Ecommerce growth 1.5.0 Registry successor 验证

日期：2026-09-12

## 结论

`solution.ecommerce.growth@1.5.0` 已用首装持久 Ed25519 trust root 完成 canonical Registry `draft → validated → published`，随后重放为零 mutation。运行配置已持久化 server-owned signed bundle root、trust-root 文件与 `linux/arm64` platform，但本波没有升级或启动 Installation。

## 首次拒绝与修正

首次 v1 apply 在 `create_version` 前因 bundle `displayName` 与现有 Registry identity 不一致被拒；只读复核确认 1.5.0 版本数仍为 0，只有数据库备份和仓外签名树产生。修正后 1.5.0 继承 1.4.0 的稳定 displayName，1.4.0 tree/backend hash 继续为 `4dc6cf...` / `959f15...`，1.5.0 backend 仍为 `0d9a0b...`，source tree 更新为 `34446f...`。Registry 校验没有被放宽。

## v2 build / qualification

- build HEAD：`da3db79605d0b0fdf1c7e6cd856398e6dbf38f15`
- output tree：`sha256:ebadbd7c49105dac011c849fc53807d1963ab4bfc41e57ec23f2229a97968cfc`
- growth content：`sha256:6a547118c5fe129cc4d9bb10c0066a9a503ee949cc67ce1e57105a0c70f3edab`
- growth config/image：`sha256:82a77ffdef25eff0663a9f701a7eac640230e14b98a425d4e4f0355db39e21a0` / `sha256:010569e2adbeecf20f053991cc0cc5304d40dbbea982b563c056622a73d603ea`
- qualification snapshot：`sha256:b6e747f43a390e2e08d5cb6aba228ecfe6f358595efdb6ddbb436127de096704`
- 4 bundles、3 runtime admissions、3 schema requirements、8 modules、12 operations 与七类 tamper rejection 全绿；临时签名未持久化。

## Registry apply / replay

首次 apply 使用 `a0v-local-ecommerce-canonical-v1` 和 trust-root revision `sha256:fc8d449e...`，生成同时包含 growth 1.4.0 与 1.5.0 的 v5 signed tree。Registry mutation 为 create=1、validate=1、publish=1；最终唯一 1.5.0 published content hash 为 `sha256:6a547118...`。

replay mutation 为 create=0、validate=0、publish=0；signed tree 五个 coordinate 与 `.env` 三项配置均 exact 重放。发布前后 Installation 总数 1、正租户 1、负租户 0；当前正租户 Installation 仍为 revision 3、state `approved`、growth 1.4.0，证明没有把 Registry 发布误作安装升级。

项目 `.env` 只增加 `AOS_BUNDLE_ROOT`、`AOS_BUNDLE_TRUST_ROOTS_FILE`、`AOS_EXTENSION_RUNTIME_PLATFORM`，每项恰好一次且非空；文件受 `.gitignore` 管理，Receipt 不包含任何私钥内容。18436 临时 Registry 端口已清理。

## 验证与边界

旧首装、successor、Candidate、Builder 与 control wiring 合计 36 项测试通过；Python 编译与 `git diff --check` 通过。环境没有 Ruff 可执行文件，因此没有记录 Ruff 结论。

本结果只完成可解析、可验证、可重放的 1.5.0 Registry release。下一波必须创建新的 exact Composition lock 与 maker/checker Installation successor，再按 runtime apply/verify/enable 状态机激活；在此之前真实租户仍运行 1.4.0 approved 配置。
