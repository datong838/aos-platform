# D02 固定请求与转换验证

2026-09-11，A0V-D02-GENERATION-BINDING-20260911；基线9bd2f39d。

新增固定aos.diagnosis-proposal/v1请求：完整Insight canonical hash、同库存Bundle、Evidence r1与正文hash、来源cutoff、不截断16000字符限制。临时Disclosure元数据不进入模型文本，重新授权相同不可变来源保持请求一致；读取/出境权威仍须运行时复验。

纯转换绑定原SUCCEEDED attempt、actor/tenant、Provider/Usage、完成时间、text Artifact与答复hash、原Executor request hash，生成稳定tenant+attempt Decision r1并绑定Insight/来源/生成Artifact。Decision新增可选Artifact引用，None时省略以保留历史序列化hash。

新模块先缺失报错；实现后19新专项，和解析/合同/旧draft首轮122通过；扩大到D03生成/Receiver/Worker/Source/Owner/approval/完整PG依赖图累计215 passed、7既有警告、退出0、4.07秒。git diff --check通过。测试覆盖来源/正文/request/actor/租户/凭据/未知状态/超限反例及重新授权请求稳定、旧Decision无新空字段。

本波新D02路径仅纯转换，没有DB接收或真实Provider调用。原PG回归不等于新D02持久接收验收；无主库写入、API重载或push。JDBC退出closed-stream既有日志未改。

下一波立即推进：D02从原私有答复、真实AgentRun/Artifact和当前Insight/授权来源读取，事务锁+既有Decision Owner保存/回读/重放。D01 MethodRevision权威缺口登记保留；真实源/安装配置、三阶段宿主与自然首链/八场景未完成，230 L0挂起。
