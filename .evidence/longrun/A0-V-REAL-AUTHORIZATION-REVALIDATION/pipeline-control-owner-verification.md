# 管道运行控制Owner验证

2026-09-12，基线dbdf739d；m1单写者。

新增pipeline_runtime_control_owner.py：记录严格编解码，校验完整draft/顶层列/selection/hash/前序/request hash；只有固定SourceSelectionOwner的run_current检查通过后才追加。控制公共上下文必须与来源选择完全相同，不能改预算、范围、期限。安装锁内同key同请求回读、同key异请求/陈旧previousRef拒绝；控制消费还检查同目标最新修订，旧控制或旧来源选择不能被消费。操作保留调用者事务并拒绝异步逃逸，无源读取、ScheduleRun、启用行为。

新增单元和PG组合测试。单元最初缺模块RED，8项初版通过；Owner和数据库组合22项通过。审查补充True==1风险：新增两个记录revision布尔替换测试均先失败；现要求实际payload规范摘要、重建摘要和存储hash三者一致，旧来源选择codec同步最小修复。最终控制codec/Owner/来源选择/表约束/合同 **98 passed**，5.22秒，7个既有警告。AR2 ar2-7 1796/158/93，五类错误数组为空；git diff --check通过。

PG组合包含真实两层Owner、真实表/事务/FK；最底层当前资产权限仍为命名测试替身，不能称实租户全组合验收。真实18435库未迁移，新服务未挂HTTP/生产工厂，P01未启用，经营首链未完成。

旁证：本波只读复查5173/ontology、8434/、18181/v1/health均200；这只证明页面/API在线。

下一波复用现有运行连接和安装控制平面接生产服务工厂，检查当前授权全组合及部署所需权限；随后绑定ScheduleRun、唯一原始输入和有界读取。不得通过另一个身份或权限包装器绕过拒绝。不push，230 L0挂起。
