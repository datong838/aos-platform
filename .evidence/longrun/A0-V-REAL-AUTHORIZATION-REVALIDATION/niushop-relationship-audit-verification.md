# 同批真实业务关系审计


SC4-5g1：同批真实关系审计完成。15测试通过（4.55秒）；真实09:07:08.053263Z–09:07:09.575589Z同一InnoDB只读事务12类型，统计保存real-relationship-audit-20260914.json。235明细/203普通支付/19发货均匹配父订单；订单号和memberId交叉字段235/203/19无不一致。235明细自身时间均未知，但父订单创建时间均可用；其中69关联软删订单。32订单、1评价缺少当前范围客户，不得客户质量宣绿。65商品分类当前诊断解析拒绝，原源Goods.php:2120–2121使用前后逗号封装，下一波核实/严格支持该格式。源schema实际有weapp_id但P05未映射，后续候选需按原schema/masking补齐，不能推算或读取weapp_openid。
正式关系写入/客户修复/窗口读模型/Fulfillment仍未完成；不跨店扩读、不补造客户、不以重复统计充当推进。下一项：分类分隔格式严格解析修正及对应真实重验，再包内关系声明及P05关联字段候选。

开发诊断，不是正式质量Receipt。源行未持久化，模型及外部业务调用为零。软删端点：SKU-Product11、Shop-Product8、Order-lines69、Line-Product36、Line-SKU36、Order-Customer55、Review-Product1、Review-SKU1、Order-Payment61。matched包含软删关联，不能当active关系覆盖率。

旧ec_link_builder.py订单明细goodsId与候选productId不符；本审计明确使用实际字段。Order.fromWeapp当前unsupported；Shipment追踪/Review正文/SystemConfig值明确不覆盖。
