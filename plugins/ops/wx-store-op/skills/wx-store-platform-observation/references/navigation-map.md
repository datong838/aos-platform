# 微信小店后台导航地图

入口：`https://store.weixin.qq.com/shop/home`。登录由用户完成。

## 店铺与商品

| 一级域 | 页面 | 稳定路径 |
|---|---|---|
| 店铺管理 | 店铺信息 / 装修 / 品牌 / 类目 | `/shop/setting/profile` / `/shop/setting/homeManage` / `/shop/brandAndCat/brand/home` / `/shop/brandAndCat/category/home` |
| 店铺管理 | 成员 / 客服 / 经营成长 / 体验分 | `/shop/staff/storehome` / `/shop/customerservice/home` / `/shop/setting/growth` / `/shop/setting/rate2` |
| 店铺管理 | 违规 / 投诉 / 诊断 / 关联账号 | `/shop/violation/home` / `/shop/complaint/home` / `/shop/shopdiagnosis/home` / `/shop/softchain/home` |
| 店铺管理 | 虚拟号 / 黑名单 / 客诉工单 | `/shop/waybill/privateNumber` / `/shop/setting/blacklist` / `/shop/complaintticket/home` |
| 商品管理 | 商品列表 / 商品内容 / 合集 / 非卖商品 | `/shop/goods/list` / `/shop/goods/content` / `/shop/setting/productSet` / `/shop/goods/giftList` |
| 商品管理 | 商品成长 / 商机 / 货源市场 | `/shop/goodsSubFunction/qualificationScore` / `/shop/goods/opprotunity` / `/shop/supplyMarket/home` |

`/shop/goods/entry` 是创建面，默认不进入。已有商品编辑只能在明确授权后从商品列表单目标进入。

## 订单、配送与售后

| 页面组 | 稳定路径 |
|---|---|
| 订单 / 发货前变更 | `/shop/order/list` / `/shop/order/shipTools` |
| 配送 / 快递地址 | `/shop/address/deliveryMgmt` / `/shop/address/expressAddressMgmt` |
| 评价 / 电子面单 / 打单 / 在线寄件 | `/shop/evaluate/home` / `/shop/waybill/admin` / `/shop/waybill/printBill` / `/shop/waybill/allToAll` |
| 同城 / 代发 / 供货 / 风险拦截 / 物流 | `/shop/waybill/intracityDelivery` / `/shop/supply/consignmentOrderList` / `/shop/supply/supplierOrderList` / `/shop/riskcontrolcenter/riskorderblock` / `/shop/logisticsservice/home` |
| 售后处理 / 申诉 / 保障 / 助手 | `/shop/aftersale/home` / `/shop/aftersale/appeal` / `/shop/aftersale/guarantee` / `/shop/aftersale/autoHelper` |
| 退运费 / 小额打款 / 售后设置 | `/shop/aftersale/freightCompensation` / `/shop/aftersale/smallTransfer` / `/shop/aftersale/setting` |

## 推荐、营销与增长

| 页面组 | 稳定路径 |
|---|---|
| 推荐流 / 推荐洞察 | `/shop/platformrecommend/recommendationFeed` / `/shop/platformrecommend/recommendRanking` |
| 搜索运营 / 搜索词洞察 | `/shop/platformrecommend/searchOperation` / `/shop/platformrecommend/searchranking` |
| 礼物 / 直播同价 / 价格监控 | `/shop/marketinggift/sendGift` / `/shop/platformrecommend/liveSamePrice` / `/shop/marketing/priceManage` |
| 优惠券 / 限时抢购 / 直播专享价 | `/shop/marketing/coupon` / `/shop/marketing/snapup` / `/shop/marketing/precheatPrice` |
| 一起买 / 买赠 / 评价有奖 / 搭配购 | `/shop/marketing/groupBuyHome` / `/shop/marketingkol/gift` / `/shop/marketing/commentGift` / `/shop/marketingkol/collocation` |
| 闪购 / 平台活动 / 物料中心 | `/shop/marketing/flashSale` / `/shop/marketingkol/activity/home` / `/shop/marketingbase/materials` |
| 老客复购 / 会员营销 | `/shop/useroperation/repurchaseTool` / `/shop/member/home` |
| 投流素材 / 推广效果 / 加热 / 投放 | `/shop/advertisement/material` / `/shop/advertisement/promotion-effect` / `/shop/channels-promotion` / `/shop/promotion/` |

## 优选联盟、保障与经营数据

| 页面组 | 稳定路径 |
|---|---|
| 带货者 / 机构 / 活动推广 | `/shop/shopleague/home` / `/shop/shopleague/head-supplier` / `/shop/shopleague/event-promotion` |
| 合作 / 专属营销 | `/shop/shopleague/coop-manage` / `/shop/finderitem/home` |
| 带货者广场 / 机构广场 | `/shop/findersquare/recommend` / `/shop/ec-agency/market/home` |
| 联盟规则 / 联盟数据 | `/shop/shopleague/league-rule` / `/shop/shopleague/contact-info` |
| 7天无理由 / 运费险 / 发票 / 先用后付 | `/shop/platformservice/refund` / `/shop/insurance/home` / `/shop/bill/home` / `/shop/platformservice/useNowPayLater` |
| 坏损包退 / 假一赔三 / 先检后发 / 抽检 / 价保 | `/shop/platformservice/badPay` / `/shop/platformservice/fakeOnePayThree` / `/shop/platformservice/qic` / `/shop/violation/spotCheck` / `/shop/platformservice/priceProtection` |
| 账户 / 流水 | `/shop/funds/home` / `/shop/funds/moneyManage` |
| 交易 / 商品 / 人群 | `/shop/statistics/transaction` / `/shop/statistics/product` / `/shop/statistics/collect` |
| 电商罗盘 / 经营工具 / 运营服务 | `/shop-faas/mmecnodecompasscommon/thirdParty/shop/loginCompassByShop` / `/shop/servicemarket/home` / `/shop/merchant-market` |
