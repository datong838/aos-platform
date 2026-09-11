# D01描述性方法适用性验证

2026-09-11，m1 68d1f556，AOS-000573。新增纯require_portrait_method_applicable，重验Method/MetricDefinition完整hash、scope、Query request/result hash与同一cutoff；原始来源按身份去重、拒绝同源多版本/unknown freshness，按各原始source.cutoff检查方法最长期限，不使用query创建时间替代源时效。没有默认DB/Provider/页面ready/业务数值输出；方法适用不能替代完整质量与权限检查。

先测试模块缺失失败；最终19项新纯测试通过。134相关测试通过（方法权威、D01正式输入、Query来源、QueryEvidence生产、材料披露），7条既有警告和退出后的JDBC日志流关闭错误，退出0。无主库写入/迁移/模型调用/API重载。

范围对账：本波只完成方法适用性，未把QualityEvidenceStore存在视为测量生产已接通。现有CanonicalPopulationReader完整上限99对象，后续正式业务聚合必须有全量来源证明，禁止截前99条。QueryEvidenceProducer只支持原始Evidence来源，Dataset/其他来源未支持。原计划中更大的完整指标质量输入仍在后续清单，不能因方法检查通过进入模型生成。

真实源核查见source-agent-recovery-verification.md：空SSH agent已从既有钥匙串加载身份成功，条件变化后只核验一次仍被服务器拒绝，未建隧道/读数据；继续依赖服务器接受的原SSH身份或原连接配置，不重复当前失败认证。

下一波：固定业务聚合及完整质量/来源合同，接D01可信画像、三阶段宿主/实际配置，再真实经营首链/八场景与连续观察。不push，230 L0挂起。
