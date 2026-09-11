# 人工阶段决定契约验证

2026-09-11，基线9d89d2f9，AOS-000573。

确认现有Eval通过只输出request-human-stage-decision，ReviewIssue负责失败问题而非通用人工通过。新增严格StageDecisionRevision与纯适用性检查，绑定运行/Plan/StepAttempt/分析对象/原Artifact/Eval/责任计划/human principal，接受有效期最多7天，其他决定无执行期，修订沿用精确prior。该契约不读数据库、不自证人工身份、不授权派发。

新增30项与旧分析/评审契约联合48通过；覆盖各绑定/hash/跨scope/过期/未来/非accept/非human/旧prior/严格嵌套版本。diff检查通过。7既有框架警告、退出JDBC日志关闭错误，退出0。无主库写入、迁移、Provider调用或push。

下一波领域Owner、不可变修订/Receipt/RLS、当前人类责任人及正式Eval/原Artifact/检查点读取，之后才接worker放行。真实首链与八工作台尚未完成。
