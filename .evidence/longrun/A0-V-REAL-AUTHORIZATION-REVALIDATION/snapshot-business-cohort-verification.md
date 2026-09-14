### SC4-5j1 业务样本选择验证

新增纯业务群体selector：完整声明12类（通用规则也可用于较小已验证组）的snapshot/own-time/parent-time；绑定原关系hash，父时间必须使用原策略已声明positive-id关联。可选known/accepted状态明确，原始快照/历史不改；known范围外或显式删除才excluded，缺父/坏时间/未来时间/未知状态留unknown。observed=excluded+eligible，eligible=included+unknown，unknown不能当有效分数。窗口[start,end)，非历史状态重建。

先Red模块不存在，后样本/原关系质量/原正式需求质量共61项4.55秒通过（8warnings）。5近期/120历史/60删除订单、39上架/18下架/8删除商品为真实聚合规模构造的单测，非再读source；父订单时间替代未知行时间仅用于业务归窗，未写回伪造createTime；缺父与非法ref仍保留质量分母。编译hash/漏类型/重复规则/未知父/未声明关联/状态集合/窗口边界拒绝。AR2扫描1930/187/93五类错误为空，无主数据/安装或新外部调用。

下一波SC4-5j2：冻结1.18基础上生成1.19候选，新增initial_store_analysis业务群体策略：Product在售子集，Order创建时间窗，OrderLine/Shipment/Payment用已声明Order关联与其创建时间；Shop/SKU/Category/CustomerLite/Weapp/SystemConfig/ProductReview是当前观察维度（Review明确不代表近30日评价统计）。保留全raw供关联/历史；规则不改旧DataRequirement语义或替代逐事实字段质量。SC4-5j3再从原analysis上下文读取实际pending DataRequirement，绑定其window/purpose/current head/生命周期与安装导出cohort策略，使窗口不是调用方手填；随后正式测量与消费者。
