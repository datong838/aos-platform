# SC4-5l6l ProductEvent 已签名后继包与十操作分派方案

日期：2026-09-16  
基线：`e0868ea9`  
owner：`m1`；不 push；230 L0 挂起。

## 已核实阻断

当前正租户运行的 `solution.ecommerce.growth@1.8.0` 是 2026-09-13 冻结的只读 UI 后继包。其已签名树没有 `ecommerce_product_event_schedule.py`、`ecommerce_product_event_binding.py`、`ecommerce_product_event_command.py`、`ecommerce_product_event_control.py`，也没有分析启动与编译蓝图两个运行模块；注册入口只声明原九项增长操作和 `analyst_workspace_view_v1`。因此当前 SourceSelection、RuntimeControl、ScheduleControl 与 Case 即使都有效，也不能证明安装包能保存、启停 ProductEvent 策略或自然启动分析。

平台侧已经实现 `ecommerce_growth_event_control` 的专用 Host、审批和路由，但当前分派组只有九项。`a0v_044` 只允许数据库锁函数接受完整九项或完整十项，并不会创建第十项绑定；Canonical Router 在没有真实绑定行时必须拒绝。现有 cutover prepare/commit/rollback 又固定九项，不能用手工 SQL 插入或把测试迁移冒充生命周期授权。

## 目标与方案

先生成不可变 `solution.ecommerce.growth@1.9.0` 候选：以 1.8.0 冻结树 `sha256:718548ad92a3715891b4b84060f0a2f22ad4baf6e492195573738e49c40ac8c4` 为唯一基线，保留全部七工作台导航/UI、经营参谋只读页面与历史业务文件；只追加已经逐步评审的 ProductEvent 四模块、分析启动/编译蓝图，更新应用组合，并把注册入口扩为十项增长操作加经营参谋读取。候选本身不安装、不签名、不授权、不修改数据库。

随后新增 receipt-first 的可选分派扩展协议。它只允许当前已安装、已签名、ready/enabled/unfenced 且清单确实声明 `ecommerce_growth_event_control` 的增长包，在原完整九操作组上追加这一固定操作；请求必须绑定当前安装代次、execution epoch、runtime revision、cutover group revision、签名 release 与专用当前审批。数据库函数在串行事务、租户会话和 advisory lock 下完成一次 CAS，写不可变 Receipt；重复同请求回放，漂移拒绝。逆操作也必须 receipt-first，先 fence/drain 再删除可选行，供卸载、回滚与后继切换复用。

增长包 E→F 切换采用安全顺序：先构建、资格、签名、注册、安装并验证 F；若 E 已有第十项，先正式收缩该项，再按现有九项 rollback 回到 legacy；按现有九项 cutover 激活 F；最后通过新协议扩展第十项。这样不放宽历史九项 cutover 合同，也不让十项状态卡死回滚。

## Rules

1. 方案、清册和固定源 hash 先提交，之后才编码；历史 1.8 候选、已签名根和运行目录均不可修改。
2. 1.9 候选只允许改变 `bundle.yaml`、注册入口和八个自身引用；只允许新增六个领域模块，并以已评审源文件固定 hash 覆盖应用组合。任何额外差异失败关闭。
3. 注册必须精确为 14 项导航/UI、原九项增长 API、固定 `ecommerce_growth_event_control` 和 `analyst_workspace_view_v1`，共 25 项；ProductEvent 与分析构造通过 SDK 纯运行测试，不连接 Host 或数据库。
4. 第十项分派只能由新的专用协议管理；不手工写 `extension_operation_dispatch_binding`，不复用普通注册回执或 cutover approval，不接受任意 operationId。
5. 原九项 cutover 语义保持；十项扩展在激活后执行、收缩在 rollback 前执行。异常结果先读取 Receipt，未知结果不换 key 重发。
6. 正租户固定 `org-org/dev-project`；`dev-org/dev-project` 只做零写隔离检查。源库只读；不产生发布、触达、投流、价格、库存或履约写。
7. 新包真实安装后仍需重建与 F exact 绑定的 SourceSelection、RuntimeControl、ScheduleControl、Case/Run；旧 E authority 不自动继承。
8. 每一子步测试、方案一致性检查、风险检查、证据文档和独立提交；完成本波后自动进入真实安装切换波次。

## 代码和资产范围

本步新增：

- `scripts/prepare_ecommerce_growth_1_9_candidate.py`
- `services/aos-api/tests/extension_runtime/test_prepare_ecommerce_growth_1_9_candidate.py`
- `bundles/candidates/ecommerce/solution.ecommerce.growth/1.9.0/**`
- 本方案与候选验证文档。

后续分派扩展子步预定修改范围：

- `services/aos-api/alembic/versions/`：新增 append-only 可选分派 Receipt、函数和 RLS 迁移。
- `services/aos-api/aos_api/`：新增固定 ProductEvent 分派扩展合同、Store/Service 与专用控制入口。
- `services/aos-api/tests/extension_runtime/`：数据库、幂等、租户隔离、回滚顺序和 Router 测试。
- current 构建、签名、重装执行器及其对应测试：只新增 growth 1.9/F 路径，不改旧回放语义。

## preHash

- growth 1.8 候选树：`sha256:718548ad92a3715891b4b84060f0a2f22ad4baf6e492195573738e49c40ac8c4`
- 1.8 `bundle.yaml`：`75efe478e04d3b9d9691e1a9e5522d58b5b2e27cfcdc8af6ef367c34842e2c53`
- 1.8 注册入口：`479278aa83823bc1f1b82dde92cf4de30e071baf0898d3e6a138daf2805c2883`
- 当前应用组合源：`828bdac469a72f3a99776539655df0e358858b4ad09f0d5eda380d3740544a9f`
- 分析编译蓝图源：`efad9be76309d29cd8d4987f72c4b1625829257cde5416fab1b87dfc287512a8`
- 分析启动源：`c324568193aab81ef5cb2495ec332d22b77e842c7c7433a2e6e17f0cd4684d48`
- ProductEvent binding/command/control/schedule 源：`f5daff339d18214864a78a01767d6dc7b8f2a6fdd9edfb8ad6d40e45e6abe011`、`44b216eee44d4dceb6700e242c5630bd9b2320f4e8ef4f01ce973e7fcbb371d3`、`b7b392d3f85dc85cc0b96d84b8ee8517239da312d85a8576197dda76c288b82b`、`07cc9387bee74bcc9f66cdcfead0fb39ca621689058abfb6a408f736285e51ed`
- 新脚本、测试、候选树及后续协议文件：`NEW`。

## 本波六步退出条件

1. 当前服务、正租户 E 安装、签名 1.8 内容和九项分派事实重验。
2. 本方案、清册、preHash、失败关闭与回滚顺序提交。
3. 1.9 候选一次生成，精确文件差异、25 项清单和 SDK 纯运行测试通过。
4. 可选第十项分派协议完成隔离数据库测试，不改变主库。
5. 1.9 四包 profile 构建、资格、签名和 Registry successor 完成，历史字节保持。
6. F 全生命周期、九项切换、第十项扩展、F authority 重建完成；自动进入下一波真实策略启用和自然 Occurrence。

## 完成边界

本方案关闭的是“源代码已有但已安装签名包缺失”以及“第十项没有正式生命周期”的阻断。候选测试通过不等于安装完成，安装与分派完成也不等于业务首链完成。只有 F 下真实数据更新自然产生唯一 Occurrence/Run，并继续经过分析、exact 评审、内容任务、能力约束、产物、人工评审续跑、复盘和 Wiki，才接近长程业务目标；之后仍需扩展到八工作台真实场景并连续观察。
