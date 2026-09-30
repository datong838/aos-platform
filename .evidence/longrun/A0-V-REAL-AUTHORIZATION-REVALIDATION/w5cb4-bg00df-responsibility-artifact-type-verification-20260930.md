# W5CB4 BG00df｜签名职责 artifact 类型门验证

## RED→最小实现

先按文件级方案在 `test_aip_responsibility_template_authority.py` 增加负例：安装/签名/Registry 行均匹配时，production profile artifact 被伪标成 `ResponsibilityTemplateRevision`，旧 `InstalledProductionProfileResolver.resolve` 返回 true；单测 exit 1，1 failed/1 passed。旧正向测试也用 production profile 字段却声称职责模板，复审后改为如实验证 `ProductionProfileRevision`。

生产源码只增两行：当 ref 类型为 `ResponsibilityTemplateRevision` 时复用既有 `_load_verified_bytes` 的路径/字节 hash/安装签名门，随后要求 `MediaResponsibilityTemplate` 精确 schema 可解析。当前已签名职责 artifact 家族是 media；非 media 未来版本必须另立 schema/签名合同，不借 profile 字节通过。历史 BI 本地兼容 ref 分支未改，不把它计为当前签名来源。

## 可复核结果

- 专项与相邻：`AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --disable-warnings services/aos-api/tests/aip/test_aip_responsibility_template_authority.py services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py services/aos-api/tests/test_w2b_production_contract_api.py services/aos-api/tests/test_w2a_production_contract_api.py` → exit 0，35 passed。
- BI 相邻：`test_ecommerce_business_investigation_aip_readiness.py`、`test_ecommerce_business_investigation_aip_composition.py`、`test_analysis_compilation_blueprint_port.py` → exit 0，36 passed。
- `py_compile` 与 `git diff --check` → exit 0。真实 media 模板字节作为隔离 release mirror 测试固定：精确 ref 正向，错 digest、profile schema 伪装负向。
- 当前库、已签名 1.11.0、Host/worker 均未修改；无 browser-pilot 正向验收。当前首链依然缺正式三身份/Host/八配置/active 安装及 BI 签名模板。

## 下一波

BG00dg 要先从 231-2 和现有六角色 blueprint 冻结新的 BI 职责模板 schema/manifest 合同、当前安装升级/回滚门，再在独立新候选版本中做 RED/最小 artifact；本波不复制或重签 1.11.0。所有 assignee 仍由正式当前 AgentInstance/Receipt 给出，不能随模板自填。
