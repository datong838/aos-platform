# W5CB4 当前源码持久签名包子波计划（2026-09-27）

## 上位方案与现场

- 复习 `a0-v-canonical-ecommerce-first-install-plan.md`、当前源码预览计划及栖月汇首链：安装必须经过可信签名/Registry/职责分离，页面 HTTP 200 不等于可用。旧首装执行器只绑定 2026-09-10 的 1.1/1.4 包和旧备份/目录，不能直接作用于当前产物。
- `m1@c805c331` 当前构建产物为 core 1.4、Niushop 1.23、growth 1.11、operations-base 1.2，外置目录 `/Users/ddt/work/projects/ai_agent/.aos-current-build-BsJyrJ1r/bundles`，构建 Receipt SHA256 `9ca926aa93109c7e9d9f1d246fac82ec354ea4f0513f4e836d185564a64fb6cc`。仍未签名/发布/安装，8080 隔离克隆目录报 MANIFEST_INVALID。

## 本子波文件级清单与顺序

1. 在 `services/aos-api/tests/extension_runtime/test_sign_ecommerce_current_candidates.py` 写 RED：不允许源构建目录/Receipt 摘要或版本漂移、已有不同签名根被覆盖、私钥/签名树进 Git；重跑 exact 只读回放。测试夹具带 `AOS_TEST_RETAIN_DATABASE=1`。
2. 新增 `scripts/sign_ecommerce_current_candidates.py`，只处理外置当前 build tree：精确校验当前 profile、Receipt、tree/content hash 与源码 commit 绑定；创建仓库外 0700 state、0600 Ed25519 私钥与 trust-roots.json；签名到全新保留目录，现有路径不删除/覆盖；用 `ManifestLoader + ReleasePolicy` 对四包独立回读。签名材料正文不写日志/证据。
   首次独立回读发现 growth `1.11.0` 源候选缺 `bundle-evals.json`，ReleasePolicy 正确拒绝。补充由实际专项测试支撑、明确不代表 runtime ready 的 eval 证据；随后在**新**目录重新构建并签名，不改/覆盖已保留旧构建与两次失败签名目录。涉及 `bundles/candidates/ecommerce/solution.ecommerce.growth/1.11.0/evidence/bundle-evals.json` 和该版本专项测试。
3. 专项及相邻回归、无删除/密钥泄漏复审；在全新外置 state 实跑签名，记录 key id/revision、签名树摘要、四包内容摘要和零 Registry/Installation/Provider 效果。
4. verification 落盘，m1 精确提交；再进入“全新隔离库 Registry/Installation”下一波，不把签名视为安装完成。

## 停止条件

Receipt 与树/源码不一致、源目录已有未知签名、旧 key/trust 漂移、任何未知写入、需要读商城源/原 12 Run 或要删除现有对象时，在动作前失败关闭并记录。原 `aos_meta_head` 与当前 8080 不写、不切换；无审批/配置权威时不启 Runtime。
