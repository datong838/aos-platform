# SC4-5e1 SKU完整快照候选

2026-09-14；基线8aed3e4f；m1不push；子Lease A0-V-SC4-SKU-SNAPSHOT-CANDIDATE。

新增prepare_niushop_sku_candidate.py与platform.ecommerce.niushop/1.6.0。原1.5.0树hash e25d7e781db3b03b72cf8443167d9536b2b1e9aad01aa385e4cd96d0ad4edfec保持不变；新树hash 891b9312ecd040d19388e624fc40d636f08e2c567e56487650283a38aab6b0c6。相对前版仅bundle.yaml、p03-product-sku.yaml、bundle-evals.json三处变化。

SKU使用已支持的v2全店快照，保留下架/显式删除与源modify_time/create_time，原非负/脱敏约束保留；goods_id→productId保留，sku_no→barcode沿用ec_normalizer与ontology原映射语义。首轮canonical验证发现缺barcode，核对原规范后修正，不填造条码。关系hasSku/孤儿校验尚未接入，候选明确relationshipMaterialized=false。

11 passed/7既有警告/5.17s。生成后的Shop/Product/SKU静态评估均通过；SKU包含原状态、源时间、精确金额、父键保留及跨店/重复键/负库存/未知状态/缺时间/额外字段拒绝。首轮3项因脚本尚未实现失败，随后1项canonical缺barcode已修复。测试全部合成，不计真实采集。

AR2 1908/187/93五数组空；diff-check通过。未构建新镜像、签名、发布或安装。候选中沿用的旧运行镜像/发布材料不代表新版本已资格审查，后续完整构建重新出证后才能发布。主库仍Shop/Product两类，本波不提高主租户物化覆盖率。

下一：剩余9类映射能力（优先分类与订单）及关联/时间语义。分类无更新时间、OrderLine创建时间原资料全0，不能伪造源时间；先采用明确观察语义或关联原订单时间的受控口径，再真实采集和Fulfillment。父级FULL-STORE-SNAPSHOT任务继续。
