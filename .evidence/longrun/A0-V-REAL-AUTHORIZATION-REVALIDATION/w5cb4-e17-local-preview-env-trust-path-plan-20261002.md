# E17 本机预览 .env 信任根路径修正计划

## 来源与边界

复习 231-2 签名来源、E17 当前正式来源审计及每日当前卷重启方案。当前 `.env` 的 `AOS_BUNDLE_ROOT` 是已签名 pinned preview 树，`AOS_BUNDLE_TRUST_ROOTS_FILE` 却指向不存在的 09-10 历史文件；当前启动脚本会从 pinned signing Receipt 覆盖进程中的两项，所以预览仍健康。该修正只消除本机预览配置漂移，**不**建立正式 Growth1.13 signer/checker、外部 OIDC 或 Host 授权。

## 文件级最小动作

- 仅改被 Git 忽略的仓库 `.env` 一行：`AOS_BUNDLE_TRUST_ROOTS_FILE` 指向当前 pinned signing Receipt 指定的 `.../.aos-current-build-pyGkqQ/signing-state/trust-roots.json`。`AOS_BUNDLE_ROOT`、数据库、身份、worker、Host 与其他配置均不改。
- 写前核验旧文件不存在、新文件存在且当前签名预检 GREEN；写后读回这一行与文件 SHA，重跑同一预检、健康/ready 与浏览器禁入。若任一失败，恢复原单行值。
- `.env` 含其他本地配置，禁止全文输出、提交或复制；验证记录只包含两条非秘密路径和哈希。

## 退出条件

本机预览路径自洽、预检与页面禁入仍 GREEN；正式 E17 受限 API/Host 仍须独立正式 trust/root、OIDC、三身份、八配置、Owner/assignment。没有当前库写或签名材料升格。
