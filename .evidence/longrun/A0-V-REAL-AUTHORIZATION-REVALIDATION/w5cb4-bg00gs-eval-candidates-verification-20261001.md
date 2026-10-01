# BG00GS verification / 2026-10-01

基线 m1 49f7e650 / AOS-001059；Task W5CB4-BG00GS-EVAL-CANDIDATES-20261001。

## 实现与复审

GET /v1/aip/model-runtime/eval-candidates 从同一SQL快照读取当前draft/validated Model与Route heads；重验payload canonical hash、租户与ID/revision。返回sourceRef、expectedHeadVersion和下一active revision的targetRef，复用evaluation_candidate_ref排除Eval回指循环。executionAllowed固定false，既不保存active候选，也不生成EvalRun/Report/Gate/Receipt。

评测页改为读取上述SDK端点，严格校验引用、版本、hash、来源状态及false执行权。模型与模型路由明确“需独立执行”；端点失败显示缺证，禁止回退旧model-admin/model-catalog发现目录。原Logic执行入口未改。

复审边界：候选只是某时点观察；后续执行producer必须重新校验head CAS与全套授权，不能把此DTO当批准。当前Skill签名执行器合同只支持Skill，不能借用作Model正式执行。没有新增数据库migration、Provider调用或手工Run。

## RED、失败与最终回归

- /tmp/aos-gs-candidates-red.log：1 failed/1 deselected/6.35s/exit1；缺端点404。
- /tmp/aos-gs-page-red.log：2 failed/9 passed/exit1；旧目录无法返回原精确候选。
- 初次专项 /tmp/aos-gs-candidates-special.log：2 passed/8.37s/exit0。
- 增加鉴权与头推进断言后的 /tmp/aos-gs-backend-regression.log：1 failed/62 passed/94.87s/exit1。测试只增加revision，重复内容触发原UNIQUE(org,project,modelId,contentHash)。未修改数据库约束；测试使用缩小contextWindow的合法配置变更并重算hash。
- 最终 /tmp/aos-gs-backend-regression-fixed.log：63 passed/8 warnings/93.28s/exit0。含签名来源配置联合、未登录拒绝、JWT与租户header不匹配拒绝、读取前后Run/Gate/Receipt数量不变、新head对应新source/target及hash。
- 前端 /tmp/aos-gs-web-regression.log：4 files/87 passed/795ms/exit0；包含端点失败不fallback、不POST与严格SDK解析。该测试使用UI test doubles，只证明交互代码，不作为业务验收。
- /tmp/aos-gs-types.log：tsc --noEmit，空输出/exit0。git diff --check exit0。

后端最终命令（cwd services/aos-api，全迁移隔离临时库，串行运行）：

```sh
.venv/bin/python -m pytest tests/aip/test_formal_model_configuration_pg.py tests/aip/test_aip_model_runtime_contracts.py tests/aip/test_aip7_model_runtime_store.py tests/aip/test_aip_model_runtime_api.py tests/aip/test_aip_model_runtime_resolver.py tests/aip/test_aip_eval_authority_store.py tests/aip/test_aip_release_publication_service.py -q
```

前端（cwd apps/web，使用本地已安装Node/pnpm）：

```sh
pnpm exec vitest run src/api/aipModelRuntime/parser.test.ts src/pages/s2/EvalsPage.test.tsx src/pages/s2/W3CModelRouterInteractions.test.tsx src/pages/s2/ModelCatalogPage.test.ts
pnpm exec tsc --noEmit
```

## BrowserPilot当前页面证据

原BrowserPilot SDK连接独立8098会话，只读导航8434/aip/evals并点击“读取全部评测目标”（GET）；org-org/dev-project，未点击运行/创建套件。会话已关闭。截图已view_image核看。

页面实际显示“已读取43个目标；1类权威目录读取失败，缺失部分保持缺证”。当前API未reload新端点，此证据仅证明失败展示不冒充模型候选成功。43条原Skill/Agent目录不是Eval通过；无当前模型正向行的浏览器证据。

- /tmp/aos-gs-browser.png SHA256 60228ce4f38976db358d9b647325ca4dbf5235ad15c7900ed66d89b83a27449c
- /tmp/aos-gs-browser.txt SHA256 985b16e00d05e4bb83f7f09c903260b14cb2082ed43e2e05c9f593b3f16e35e0

## 剩余与下一波

BG00GT：沿原AipEvalRunner→Report→ReleasePublicationService检查Model/Route正式执行来源、独立身份、审批和费用/出境边界；建立首链所需的实际生产入口，不能用callback返回值或手写Gate当权威。继续原Review→TaskRun→AgentRun→首生审批→Capacity→GE held联合来源。

当前真实库未迁移/重启/API未reload，本波不证明每日重启门；正式Model Eval、Health、自然首链、八工作台与发布决定仍未完成。未启Host/worker/Provider、未读商城源、未重放旧12Run、未手工run_definition、未动230 L0。watchdog仅方案未部署，Goal仍active。旧dirty保留，不push。
