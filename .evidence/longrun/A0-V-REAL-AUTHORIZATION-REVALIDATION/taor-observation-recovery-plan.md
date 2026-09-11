# TAOR 前序观察结果恢复施工方案

2026-09-11；基线 a666d32d；AOS-000573；m1 单写、不 push、230 L0 挂起。

执行器 preHash：520203d21ea1a1b460ae51b6b7cc2407ebb7e9b7cd447f346988b555d6635d8c。

## 产品与技术依据
231-5/231-6 要求真实来源分析、方案设计及人工评审后的自动续跑。已有 D03 generation composition 可保存和恢复正式草稿，但 CanonicalTaorRunner 重启只跳过 succeeded step，丢失原 step:key 上下文。直接接 D03 将无法稳定承接前序画像与诊断。本波修复这个前置缺口，不宣称经营计划已生成。

## 最小实现
- 修改 services/aos-api/aos_api/aip_taor_loop.py：从本次受租户约束的 TaskTimeline 中解析 succeeded step 的 observe_ref，以原 taor.observe Evidence payload 恢复上下文；复用既有 canonical hash，不新增表、不复制业务正文、不重新调用 adapter。
- 精确检查 step/evidence 租户、run、stepRunId、stepKey、evidence type/id、内容哈希及对象形状。重复成功步骤、缺失/歧义/漂移证据拒绝，不能静默重跑。恢复结果仅在遍历到该计划步骤时进入 context，避免未来步骤结果提前泄露给前序。
- 深拷贝观察结果，防止 adapter 改写 timeline 内存中的证据。
- 新增 services/aos-api/tests/test_aip_taor_observation_recovery.py：新旧实例续跑等价、仅执行未完成步骤、损坏证据及隔离负例；使用自有模板的一次性克隆通过真实 Task/Plan/Run/Step/Evidence Owner 验证，不在主库制造业务数据。
- 项目上下文和 D-waves 清单追加此切片及下一入口。

## 边界、风险、退出
观察结果是历史检查点，不是当前业务授权；D03 仍须复验 current 来源/权限/预算。旧成功步骤缺原始观察证据时明确阻断，不补造。此次不调整租约、未知结果恢复协议或 Provider 重试；慢调用续租与受信工作者绑定为下一波。退出需缺陷先红、专项绿、真实隔离续跑通过、方案一致性复核及提交。回退仅撤销本波代码，不回滚/删除用户数据。API 未重载前不得声称运行环境具备此修复。
