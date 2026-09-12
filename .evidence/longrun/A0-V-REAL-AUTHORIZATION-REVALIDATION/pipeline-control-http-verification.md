# 正式审批HTTP接口验证

2026-09-12，m1基线21b4e0ea。新增pipeline_controls.py，正式domain_manifest登记548项并重新生成aggregate。POST来源选择/运行控制审批由Principal限定actor与租户，路径/草稿不符在工厂构造前拒绝；前序类型、UUID、修订及幂等头严格检查。无SQL或执行fallback，复用生产工厂及原Owner。请求限64KiB，原始JSON严格校验固定错误不回显输入；同步数据库服务使用线程池。

测试先因router缺失RED，随后专项20 passed，补前序传递/坏JSON/大小限制/真实app登记后相关103 passed（HTTP23、工厂/合同/两个Owner）。模拟审批服务只证明传输与调用绑定；Owner已有独立验证，本轮不冒充真实审批。生成器check548一致，AR2闭包1798/158/93五类错误空，diff check通过。测试中的既有重复Operation ID警告属于旧pipeline/schedule/dataset路由，未改变这些旧入口。

复核：无新数据模式、无源读取、无P01启用、无自动重发。503未知结果文案明确保留原幂等键核对。真实API当前未重启加载新接口；页面的候选/确认流程未完成，OpenAPI请求体详细schema待补齐，不能声称已完成用户可用的配置产品。此前部署的两审批历史表仍是独立存储前置条件，本波未写入它们。

下一波当前运行控制进入现有ScheduleRun/Ingress事务；原始批次恢复不重新读取源。随后正式部署与页面交互、真实P01验收。m1单写，不push，230 L0挂起。主A0-V任务及其Lease仍未完成；本文件与Git提交作为本波交付证据。
