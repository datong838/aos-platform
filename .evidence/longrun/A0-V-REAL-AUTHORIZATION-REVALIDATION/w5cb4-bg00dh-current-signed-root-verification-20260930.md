# W5CB4 BG00dh｜当前受检签名根接入职责 resolver 验证

## 方案与 RED

先读 231/231-2、BG00dg 验证、`control_wiring._current_a0v_host_preflight`、默认 `InstalledProductionProfileResolver` 与现有测试，再写本波文件级方案。RED 命令：`AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --disable-warnings services/aos-api/tests/aip/test_aip_responsibility_template_authority.py -k 'current_signed_mode or current_signed_root_pin' services/aos-api/tests/extension_runtime/test_production_runtime.py -k 'current_host_preflight_requires_api_physical_authority_and_signed_paths or current_signed_mode or current_signed_root_pin'`，exit 1，3 failed（缺签名根 pin 与 Host 接线）。

## 最小实现与结果

- `aip_responsibility_template_authority.py`：只有通过 Host 当前签名/物理身份预检才可进程内 pin 签名根；记录根目录设备号/inode，拒绝不同根与原位换代。默认 resolver 遇当前签名 receipt 或已配置 `AOS_BUNDLE_ROOT` 而未 pin 时失败关闭；环境路径漂移、包路径逃逸、错租户/安装/lock/hash 仍拒绝。显式注入临时根的隔离测试不变。
- `asset_registry/control_wiring.py`：原 Host 预检的子进程签名报告、scope、根、API 物理 DB 身份和凭证代次都通过后，才 pin 报告中的 `signedRoot`；pin 失败时 Host 仍禁入。
- 最终专项及邻接：`test_aip_responsibility_template_authority.py`、`test_production_runtime.py`、`test_ecommerce_business_investigation_aip_authority.py`、`test_w2a_production_contract_store.py`、`test_w2b_production_contract_store.py`，exit 0，83 passed，7 warnings。`py_compile` 与 `git diff --check` exit 0。
- 当前实例只读预检：`scripts/a0v_current_runtime_host_preflight.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json --preparation-only`，exit 2，`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。未启 Host、worker 或 Provider；未修改当前数据库、签名包和安装。

## 复审与剩余风险

本波只证明受检根的代码接线及隔离负例。当前正式三身份、Owner/assignment、八项配置候选仍缺；当前签名增长包也未含 BI ResponsibilityTemplateRevision，首链继续 pending。默认 resolver 的历史 BI 本地兼容特例尚在，后续应在新签名版本和合法安装链齐备后迁走。Host 关闭时，当前签名模式的默认 resolver 失败关闭，不能把 API 页面可访问或隔离测试正向当业务 GREEN。没有 browser-pilot 截图。

## 下波

BG00di 先核新 BI 模板 artifact 的候选 release 与正式签名发布路径，按不可变版本/签名/lock/安装迁移边界写方案和 RED；当前库只读，不能原位改写 1.11.0 或旧签名树。若新版本发布需要当前数据库切换，另开备份与克隆全链演练波。
