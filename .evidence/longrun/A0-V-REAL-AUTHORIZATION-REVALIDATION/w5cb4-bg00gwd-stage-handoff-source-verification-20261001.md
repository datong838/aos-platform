# BG00GW-d verification

基线AOS-001068/f15c3455；来源关联读取器，不授予执行权且未接入运行中Handoff。

## 命令与结果

cwd services/aos-api：
- RED `.venv/bin/python -m pytest tests/extension_runtime/test_analyst_stage_handoff_source_pg.py -q --tb=short`：缺新模块，collection error/exit2。
- 最小实现后专项8passed/5.08s/exit0。
- 复审追加相邻版本业务内容变更及过期accept反例；累计新增文件、test_growth_approval_handoff_source_pg.py、tests/test_ecommerce_analyst_stage_decision.py、tests/test_ecommerce_analyst_growth_plan_approval.py、test_ecommerce_review_advance_host.py：60passed/5.17s/exit0/零跳过。
- 累计有2项新增测试序列化warning，原因是model_copy内用str代替enum；改为GrowthPlanLifecycle.APPROVED后最终专项10passed/5.13s/exit0，仅保留7项既有warning。
- 两文件py_compile、git diff --check exit0。

## 复审

原Host approved读取器锁当前head并核Receipt；原Owner读历史draft并核hash；原StageDecisionStore锁当前决策并核原Receipt；原require_stage_decision_applicable核租户、时间和预期taskRun/Plan/stageAttempt。approved.priorRef必须精确指向所评draft；只排除既有批准元数据的全部业务体hash一致，正文artifact必须非空且等于accepted对象。数据时钟来自事务DB。
真实标准临时PG十项测试无关键mock，包括有效历史draft→approved、五类来源漂移、旧accept及当前revoke拒绝、非相邻后继、同相邻版本改变正文业务字段、过期accept。显式fixture草稿/决策不是客户自然生成或真实人审；原Owner put不替代外层ACL。累计旧mock单测不计自然联合。
函数没有外部IO/新授权/DB写入，未连接当前库、迁移、启Host/Provider/worker、读商城源、重放旧Run或push；浏览器不适用。

## 剩余

返回对象仅供后续受控Handoff适配消费，不能据此创建Task/Brief。签名Eval、当前职责/安装fence/来源/审批权限/预算仍须真正消费者复验。GW-b新用途待裁决，旧Issue/四Artifact与当前accepted路径错位仍未闭合，自然首链不完成。下一步先把该读取器接入既有审批后Handoff生产路径的具体方案，避免将未调用helper视为交付闭环。

## 日志SHA256
- `/tmp/aos-gwd-red.log`: `ba3423d8634307e4b6e5c35ff44344a1d9db81a0c385ad11804aa790bd920f8b`
- `/tmp/aos-gwd-focused.log`: `f8ff737293f13540ed748dda074aaa9c050dfda75fb38192d1d557b048f8c2bb`
- `/tmp/aos-gwd-regression.log`: `756785f813c3ef38efdcc29bcd599064ac485f5fdd919b6f717a6517820cf2a9`
- `/tmp/aos-gwd-final.log`: `fe2c0bb75f9a6fede5498cad9418e84ec43945f1400a400259289f2613588b2f`
