# W5CB4 BG00dg｜BI 签名职责模板严格 schema 验证

## RED 与实现

RED：`AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --disable-warnings services/aos-api/tests/aip/test_aip_responsibility_template_authority.py services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py -k 'exact_signed_bi_template or bi_template_rejects or six_responsibilities_bind'` → exit 1，6 failed，因严格 BI 模板模型/共用 blueprint 尚不存在。

新增 `aip_business_investigation_responsibility_template.py`：固定只读 BI schema/template/profile、六 slot 顺序/类型/能力/return stage，禁止 assignee 等额外字段；旧 materializer 引用同一不可变 blueprint。installed resolver 仍先核当前安装/签名/lock/artifact digest/原字节，再按 media 或 BI schema 精确解析；未知 schema/错 slot/profile 字节失败关闭。没有新增候选包、当前 Registry 或业务配置。

## 结果与限制

- 专项/相邻：上述两文件及 `test_ecommerce_business_investigation_aip_readiness.py`、`test_ecommerce_business_investigation_aip_composition.py`、`test_w2b_production_contract_api.py` → exit 0，53 passed；新增 assignee 字段负例后两文件再跑 exit 0，33 passed。
- `py_compile`、`git diff --check` exit 0。隔离临时 release mirror 中 exact BI artifact ref 正向；六 slot 缺/重/能力漂移、未知 schema、assignee 注入、错 revision/hash/tenant 负向。隔离证明不等于当前正式签名包已有该 artifact。
- 静态回读：`test -d bundles/releases/ecommerce/solution.ecommerce.growth/1.11.0` exit 1，`test -d .aos-current-build-pyGkqQ/signing-state/signed-bundles/solution.ecommerce.growth/1.11.0` exit 0。当前默认 `InstalledProductionProfileResolver` 使用仓库 `bundles/releases/ecommerce`，未绑定当日受检签名树；这是独立的可信根接线缺口，不能把本波临时 mirror 正向当当前实例正向。
- 当前库/已签名树/Host/worker 未改；历史 BI 本地兼容特例保留，尚未迁到签名 ref；首链 pending。无 browser-pilot 截图。

## 下波

BG00dh 先从当前签名 receipt/四包预检建立 resolver 可信 release root 注入与代次固定方案，隔离 RED 覆盖旧仓库目录、错签名/路径漂移/错安装；随后再独立新候选版本中加入 BI 模板 artifact 并做签名/安装迁移。不得直接读取未受信的 `AOS_BUNDLE_ROOT` 作为授权。
