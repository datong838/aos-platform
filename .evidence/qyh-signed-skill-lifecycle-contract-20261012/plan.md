# 栖月汇 Skill 签名执行生产链生命周期方案

本波是 BG00u/BG00ac 已登记后续合同调查，不是执行器交付。产品目标为电商域栖月汇八台；不删除原普通 runner 的 Skill/Model 拒绝门、不补签旧报告、不修改真实历史 Run。

## 两个候选及依赖
1. 新 Skill 专用 producer：已授权隔离设计和实现。先冻结生命周期和双签名/原子提交合同，后续精确代码波执行。正式调用依赖可信 issuer、不同 Target/Judge 身份、Owner/审批/预算/网络及独立 writer；测试身份只在新隔离数据库使用。
2. 正式登录/独立发布恢复：用户已授权，已有数据及签名包保留。当前请求既有登录配置路径，不能凭开发登录成为正式 Owner。此条件不阻断候选1的无外部效果施工。

## 本波文件与验证
文件限定本目录 plan.md、lifecycle_audit.py、observed.json、contract.md、review.md。先用 git HEAD 的精确代码识别普通执行事务、登记前置状态与生产者调用；再在已授权 tmpfs clone 18431 上两个独立 READ ONLY / REPEATABLE READ 快照，确认 cluster、实际 writer 对 Run/Event/Report/Receipt/Proof 权限。审查当前实现是否支持同事务结束状态，记录需要修改的精确后续路径。
只读调查不造业务 Run/Report、不开 worker、无迁移/服务重启。数据库禁止继承默认端口；容器 ID/镜像/无卷与 cluster 必须匹配。结果用于冻结缺口，不能作为自然首链或八台验收。
