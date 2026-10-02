# E17-a2b2b｜正式启动 selector 文件级方案

## 上位方案与当前事实

复习 231-2/231-3、E17 正式启动方案、E17-a2b2a 同代 OCI 视图。现 `scripts/a0v_current_preview_http.py` 的 `--serve` 与 `--serve-limited` 都先执行四旧版本、approved、binding0 的 pinned preview 预检；`scripts/a0v_current_runtime_host_preflight.py` 也调用同一预检。Growth1.13 原 producer 正例已有 active/current、同代 ready binding、已签 OCI 证据，但该视图只提供 `EVIDENCE_ONLY_NO_START`。当前真实实例正式 OIDC、独立身份、信任根、八配置、Owner/assignment/正式发行与绑定缺失，必须失败关闭。

## RED 和最小文件

1. `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py`：新增正式模式要求 Growth1.13 版本感知发行视图、拒绝 approved/binding0、错代/错摘要、缺签名/OCI；原 pinned `--serve` 不变。测试使用可销毁原 producer 的 PG/OCI，不以函数替身或 test-only 凭据证明当前实例。
2. `scripts/a0v_current_preview_http.py`：为受限 API 明确区分 pinned 与正式 selector。先核外部 HTTPS OIDC、受保护 API 身份；正式 selector 用 E17-a2b2a 只读视图重验当前发行、exact lock、OCI、schema，并仅返回预检证据。实际启动还需核配置与 Owner；缺任一门不得执行 `os.execve`。
3. `services/aos-api/tests/extension_runtime/test_a0v_current_runtime_host_preflight.py` 与 `scripts/a0v_current_runtime_host_preflight.py`：改为正式视图，保留三独立身份/Host assignment/八配置与 credential generation 复核；未证明 Owner 前仍 `PREFLIGHT_ONLY_NO_RUNTIME_START`。
4. `scripts/a0v_ecommerce_runtime_host.py` 的固定 Owner 拒绝只在另波原 lifecycle 同源正反链具备后改。此波不删除该门、不启 Host。

## 验证/停止线

先 RED，逐项最小实现；专项、旧 preview、旧 Growth1.12、相邻 Host/发行测试串行执行。当前库只读，不用 test-only signer/credential/假账号，不读商城源、不重放旧12 Run、不手工 Run、不碰230 L0。若发现正式 selector 需新的实质身份协议，先完成已授权且独立的拒绝路径，记录精确缺口并转 D-waves 已登记 d2b3c4f 原持久 Review Receipt 主线。当前 API/Host/worker/Provider 不因 RED 或本地正例放行。

## 实施切片与新发现

本波先完成 b1：在既有脚本加可调用、无副作用的版本感知 selector，并以原 1.13 producer 的同代 PG+OCI 和当前 approved 四旧包做正反例。它是后续正式 API/Host 的共同输入，结果固定 `PREFLIGHT_ONLY_NO_RUNTIME_START`。实际 `--serve-limited` 与 Host CLI 接线列 b2：当前没有可核验的正式 trust/root 来源、OIDC、API/Directory/Runtime/Web 凭据及精确 Owner；若直接把任意路径上的本地 trust 文件当作正式来源，会把 test-only 签名升格。b2 须先在输入合同中固定正式来源与三身份，再用原 producer 证据接线，保留 pinned `--serve`，不能只改命令行开关。
