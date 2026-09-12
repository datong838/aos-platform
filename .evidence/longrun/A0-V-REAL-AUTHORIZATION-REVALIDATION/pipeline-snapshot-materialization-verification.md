# 声明式快照转换验证

2026-09-12，基线f5e5d462。新增纯编译/转换模块，读取范围、source/target/type、required、唯一键与snapshot_materialization由包声明；无eval、无源查询、无当前时间隐式回退、无原始额外字段透传。platform/shop来自明确配置及批准过滤。Shop的status/currency/timezone为拟新包明确缺省，不冒充源表营业/币种字段。既有published 1.3.0未改。

先缺失模块RED；复核发现重复PK可被不同模板其他字段掩盖、映射filter未对照read_spec，两项测试RED后修复。转换/读取规格/有界读取相关65 passed；增加现有CoreObject内核接纳验证后转换专项32 passed。合成P01包含11映射字段+3明确缺省，createTime=0为null，UTC观察时间独立保存，properties14项进入原内核，外部键niushop:1:1。严格类型/范围/模板/默认覆盖/隐私额外列/重复键/旧无配置映射拒绝；调用方文档修改不改变已编译计划。

AR2闭包1801/158/93五类错误空，diff check通过；memory验证GREEN。只有合成数据，不是实时Schema或真实商城读取。当前1.3.0没有snapshot_materialization，解释器会拒绝；需新不可变版本声明与发布/安装变更后才能进入真实P01准备。源调用占用/原批次适配仍未接正式执行，真实首链未完成。

下一波准备新平台适配包的明确快照转换声明，校验旧包hash不变与运行镜像/注册版本一致；随后新包当前安装/配置/审批及一次有界读取→原批次保存→恢复/对象投影。m1单写、不push、230 L0挂起。
