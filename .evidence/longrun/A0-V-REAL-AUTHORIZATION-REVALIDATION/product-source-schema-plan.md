# 商品真实源结构核验

2026-09-13，基线04ac2a4d，m1主A0-V Lease。只调用现有 GET /api/datasource/sources/niushop-qyh/schemas/niushop_b2c_v5/tables/ns_goods/columns，复用当前localhost API与现有开发身份，正租户org-org/dev-project。不调用preview、业务SELECT、同步计划、修改源连接或写source配置；不显示token/凭证/自由错误正文。

成功响应必须demo=false且真实列标识唯一；对照已签名候选1.5的28选列，输出所需列的name/datatype/nullable/primary_key及缺失/不兼容项。字段注释与默认值不归档。此次元数据只表示当前字段类型，不证明商品内容、行数、状态枚举或业务变化。超时/错误先停止并保留HTTP状态/异常类，不切换SSH或直接用凭证旁路。下一步按核验结论完善P02接入方案，安全替换新旧generation须先准备不启用、禁入旧代、排空、切换，不能两代业务双跑。
