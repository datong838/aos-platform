# SC4-5e3 分类层级与观察快照候选

2026-09-14；基线07dc3077；m1不push；父Lease A0-V-SC4-CATEGORY-ORDER-SNAPSHOTS，候选子Lease A0-V-SC4-CATEGORY-SNAPSHOT-CANDIDATE。

v3新增可选严格hierarchy(parent_field,root_value)，在完整有界批次内验证所有父节点存在、无根哨兵占用和循环，迭代缓存避免递归溢出；不按输入顺序假设树序，也不生成关系。已通过1000层深链、乱序森林、孤儿、自环、多节点环与非法声明回归。

新增prepare_niushop_category_candidate.py与1.7.0候选，采用v3观察时间、pid→parentCategoryId与is_show明确状态；旧说明性custom校验变成可执行hierarchy。Product.inCategory关系仍未物化，候选明确relationshipMaterialized=false。原源字段保留，不声称源业务修改时间已知。

相对1.6.0仅bundle.yaml、p04-category.yaml、bundle-evals.json三处变化。源树891b9312ecd040d19388e624fc40d636f08e2c567e56487650283a38aab6b0c6不变，新树5641f4890a2198fd92d6eefc4e68400d90ce7030c8e8e8059a657c09de4ba069。四类静态规范对象评估通过，不代表4类主数据已接入。

94 passed/7既有警告/5.99s；AR2 1909/187/93五数组空；memory GREEN1106/1090/2712；diff-check通过。先见旧版本不支持hierarchy及缺生成脚本红测，再实现通过。所有源记录合成；未构建新镜像、签名发布安装或主库采集。

下一：订单含显式软删的观察快照口径，再剩余7类；关联、真实完整采集、Outbox Fulfillment及主业务首链仍未完成。父级分类/订单任务继续至订单子项，主库保持先前只读核对的2/12，不更新真实完成率。
