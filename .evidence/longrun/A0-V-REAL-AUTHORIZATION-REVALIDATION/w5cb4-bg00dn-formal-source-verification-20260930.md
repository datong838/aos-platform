# W5CB4 BG00dn｜当前正式签发/身份/配置来源只读审计

## 方案、RED 与最小实现

按 231-2/231-3、BG00dk/dm 复习后，先写 `test_growth_112_formal_source_audit.py`；首次 `.venv/bin/python -m pytest -q ... --disable-warnings --tb=short` 退出1，两项因正式审计入口尚不存在而 RED。新增 `scripts/a0v_growth_112_formal_source_audit.py`，只读固定当前/克隆 context、容器、数据卷、回环端口及 a0v_118；分别复核当前1.11与新1.12 signed receipt/信任根，再读取固定控制表、正租户成员去重数与八候选。只输出计数和原因码，不输出 subject/口令/商城数据，没有 apply 开关。`assess_sources` 无论计数如何均返回 `formalReady=false`，明确这是一份诊断而非正式授权。

## 可复核结果

| 检查 | 命令/范围 | 退出码与结果 |
| --- | --- | --- |
| 双库正式来源审计 | `services/aos-api/.venv/bin/python scripts/a0v_growth_112_formal_source_audit.py --current-signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json --successor-signed-receipt /Users/ddt/work/projects/ai_agent/.aos-growth-112-signing-receipt-r3-20260930.json` | 0；`CURRENT_FORMAL_SOURCE_AUDIT_SAFE_BLOCKED`、effects0、formalReady=false。当前 Registry 无 growth1.12/安装1；克隆 growth1.12 published/安装2；两侧版本均 a0v_118、Host identity/assignment/operation/binding/config均0，八候选逐项0、正租户 distinct member均1 |
| 根和凭据入口 | `.env` 只读列键及路径存在性；当前签名 receipt roots 与新 key 精确查询 | 0；`AOS_BUNDLE_ROOT` 路径存在，`AOS_BUNDLE_TRUST_ROOTS_FILE` 配置路径不存在，`.env` 无 `AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE`；当前 receipt root 不含新 1.12 key。没有读取凭据正文 |
| 原 Host 预检 | `scripts/a0v_current_runtime_host_preflight.py --signed-receipt .../signing-receipt.json` | 2；`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`，无 Host 启动 |
| RED→GREEN | `test_growth_112_formal_source_audit.py` + BG00dm clone + current install 相邻 | 首次2 errors/退出1；最末 `15 passed`/退出0；`py_compile`、`git diff --check`退出0 |

首次物理目标检查因当前 PG 有额外只读 `/backup` bind 而返回 `CURRENT_PHYSICAL_TARGET_DRIFT`；复核 `docker inspect` 发现唯一数据目录仍为权威命名卷、额外挂载只读，随后将校验精确约束为唯一数据卷及禁止任何额外可写挂载，重跑审计退出0。这是审计器误判修复，没有数据库写入或业务重试。

## 复审和下一波

原因码：`CURRENT_RELEASE_MISSING`、`CURRENT_TRUST_ROOT_MISSING`、`INDEPENDENT_CHECKER_MISSING`、`THREE_PLANE_CREDENTIAL_REFERENCE_MISSING`、`HOST_IDENTITY_MISSING`、`HOST_ASSIGNMENT_MISSING`、`CONFIGURATION_CANDIDATES_MISSING`、`FORMAL_AUTHORIZATION_NOT_PROVEN`。当前签名与克隆开发签名各自可核，但没有组织正式签发/轮换和独立 checker 来源，不能拿本地测试人物、合并 test-only root 或仅凭成员/候选计数启 Host。当前库只读，Host/worker/Provider关闭；没有商城源读取、dev-org写、旧12 Run重放、手工 run_definition 或外部效果。浏览器验收本审计不适用，未声称截图。

BG00do 转到可独立推进的首链必要产品来源：先核签名 growth1.12 `business-investigation.readonly` 模板与现有 AIP 职责模板/Plan 创建合同，文件级方案和 RED，只在 test-only 构造合法候选消费链；正式组织身份和当前实例切换仍是独立授权/恢复波。
