# 受控来源正文完整性验证

2026-09-11；A0V-DISCLOSED-SOURCE-INTEGRITY-20260911，基线a80b95e5。

缺陷先红：保持Evidence登记hash和原授权，替换返回正文，原read_disclosed_evidence_source未抛拒绝异常（DID NOT RAISE）。最小修复在返回正文前复用canonical_hash重算并与exact引用比较。

本次21 passed，7既有警告，退出0，0.99秒：原文读取12项、直接撤销7项、完整一次性PG2项。真实PG通过原Disclosure Owner创建当前allowed L3决定和Receipt，正确正文回读hash一致，错误正文在授权仍allowed时拒绝；两场景撤销后均拒绝。测试用自有模板克隆的完整数据库及合成Task/Run/Evidence，不写实际客户数据，finally删除。

旧test_a0v_disclosed_source_pg.py合法样本同步改用真实正文hash，其专用AOS_EXTENSION_PG_TEST环境本波未运行；不计入通过数量。新完整PG验证独立执行。git diff --check通过。

权限/授权层无扩张，L1/L2/L3授予、原请求Receipt/actor/当前撤销/到期检查保持；不改历史记录。旧不一致正文会被明确拒绝，不补造hash。没有Provider调用、主库写入、API重载或push。既有JDBC退出closed-stream日志错误未改，退出码仍0。

下一波回到D01/D02：使用已授权且可重算的正文构造固定分析请求，绑定指标/方法/评测和原attempt，再接可信结果保存及三阶段宿主调度。真实来源/当前运行配置、自然首链、内容人工评审后续跑、八场景与发布观察仍未完成；230 L0挂起。
