# W5CB4 BG-00c｜技能放行事件 Owner 路由验证

## 来源与最小边界

复习 231-1/9、AIP BIND-3，以及 `aip_release_publication_service.py`、`aip_skill_publication_service.py`。当前真实库 `aos_current_preview_20260927@a0v_111` READ ONLY：`org-org/dev-project` EvalSuite/Run/Report、ReleaseGateDecision、PublicationEvent、LogicPublication 均 0；37 Skill 为 evaluated，无 published Skill。新增路由只消费未来真实 passed Gate，不创建 Gate/Report，不写当前库。

## RED→GREEN

- 隔离 PG 反例 + API 合同先 RED：服务 `publish` 缺 `expected_target_type`，`POST /v1/aip/publications/skills` 为 404，2 failed。计划见同目录 `w5cb4-bg00c-skill-release-owner-route-plan-20260928.md`。
- `AipReleasePublicationService.publish` 可选 exact target kind，在 event replay 与新 Gate 两处于写入前检查；不匹配抛原有 `AipReleaseAssetUnsupported`，不放宽 Gate、EvalReport、target hash/生命周期、Receipt 或幂等门。新增技能专用路由复用同一 Owner，指定 SkillTemplate；旧 `/publications/logic` 合同不变。
- 专项及相邻 `pytest -q test_aip_release_publication_service.py test_aip_release_publication_api.py test_aip_skill_publication_service.py` exit 0，19 passed。隔离 PG 证明 Logic Gate 走技能路径零新 Event，跨类型 replay 被拒；原真实 Skill r1→r2 隔离链现在通过 exact Skill 类型门，原 Logic 发布/撤销仍通过。`compileall`、`git diff --check` exit 0。

## 复审/余险

当前实例仍没有 canonical EvalSuite/Run/Report、Gate、PublicationEvent、Logic 发布或路由策略，故不能以新 HTTP 路由声称正式 Skill 已发布、绑定或首链可运行。现有认证模型与 AIP-4 Owner 权限沿用，P0 鉴权技术债另门处理；不使用假账号/旧代/测试夹具写当前库。无 browser-pilot 可调用工具，未做浏览器截图。下一波 BG-00d 应优先追 canonical EvalSuite/Report 的产品生产路径与首链必要来源。
