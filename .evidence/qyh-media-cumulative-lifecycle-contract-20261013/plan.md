# Media v6累计合同与已有生命周期投影兼容修复

Rules：AGENTS.md、AOS工程交付、231、root8真实只读读取主线、单m1/保护dirty、原执行门不变。先方案/登记再RED和最小实现。

1/8实际证据：冻结HEAD32bd509，正常SCRAM aos_a0v_runtime_20260912、无SUPER/BYPASS、default transaction READ ONLY、原真人admin membership实际SELECT核对。8module安装读取门均过且disabled；7root返回DTO，Media返回ValidationError：legacy media view cannot carry v4 lifecycle contribution，见../qyh-restoration-successor-latest-restart-20261013/native-readonly-r3.json。此前task cockpit缺参属核验工具错误已修，非产品风险；directory/web拒绝runtime读取是原身份隔离，不授新ACL。

原因：EcommerceWorkshopMediaStudio原read在cumulative存在时使用MEDIA_STUDIO_CUMULATIVE_SCHEMA_VERSION(v6)，仍按原lifecycle.read带有效生命周期。WorkshopMediaStudioViewEnvelope._canonical_shape只允许v4/v5带lifecycle，而同validator已经允许v6带publish并必须有cumulative_gate_set；v6兼容生命周期漏项导致整root读取500，非预算/Source根因。

2/8具体目录：services/aos-api/aos_api/ecommerce_workshop_media_studio_contracts.py（仅lifecycle版本允许集合补v6）；services/aos-api/tests/test_ecommerce_media_cumulative_lifecycle.py（原真实服务composer的合法lifecycle+cumulative正向，v2/v3拒绝、v4/v5保持、blocked与产物冲突拒绝）；.evidence/qyh-media-cumulative-lifecycle-contract-20261013（RED/GREEN/相邻/冻结复审/Delivery）。D-wave登记后再编码。接口字段/schema/状态不新增，不移除validator，不调用外部动作，不改历史数据/表/签名/Owner/预算/readers，历史cumulative CURRENT标签的风险单独保留。

验证：新增服务-level案例RED精确同ValidationError；最小兼容条件→专项及media studio/source/lifecycle/cumulative相邻。方案一致性：v6合法已存在生命周期可显示，v2/v3仍不能带v4生命周期；ready/blocked字段一致性、publish/cumulative external_effects_allowed=false和release_allowed=false保持。独立Prime冻结代码与测试精确claim、tools0/消费后精确提交和准确Delivery。之后新最新HEAD重新Git冻结（旧32冻结只作旧cutoff），原runtime角色root8真正读回，再完整同卷重启与原owned SPA/browser；不把unit pass当native/business完成。

回滚：仅本文件新版本集合回退，保留原合同/用户dirty/业务数据。风险：修复只消除v6 schema拒绝，不代表历史工程evidence当前、发布或经营首链通过。
