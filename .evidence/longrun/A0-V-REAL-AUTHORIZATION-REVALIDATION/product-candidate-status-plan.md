# 真实商品经营候选状态准入方案

基线4928937e，实际65条Product中39 ACTIVE、18 INACTIVE/unknown、8 DELETED。按O1-UX7/UX9产品口径，只有state=1、isDelete=0且canonical active的商品可进入当前经营候选。全量接入仍保留下架及删除，以便观察变化。

Rules：沿用aos-engineering-delivery、m1单写、用户持续开发授权；不push，不扩大230 L0，不修改线上商城。先测试失败再最小实现。

具体新增文件：
- bundles/platforms/ecommerce-niushop/backend/ecommerce_niushop/product_candidate.py：平台包内纯函数，对可信Owner读出的单个Canonical Product按显式org/project/shop做身份匹配，返回固定原因码。拒绝错误类型、缺字段、字符串/布尔代替数字、矛盾状态；只允许ACTIVE/active/unknown=false、is_deleted=false、state=1、isDelete=0。下架与删除保留为不同不合格原因。
- services/aos-api/tests/extension_runtime/test_niushop_product_candidate.py：状态矩阵、跨租户/店铺/平台、未知/矛盾/缺失、输入不可变回归。

这不是授权验证或经营任务创建接口，不替代SourceSelection、Readiness、当前对象版本复查、预算和exact审批。事件消费者仍须消费下架/删除事件以撤销旧候选，不可因不合格就丢失事件。本波只完善数据解释契约并用保存的真实命令核对39/18/8；生产包发布安装与消费者接入在后续波次完成。

不直接改ec_ot_writer的历史状态映射：IngressJournal重校验会重新规范化原outputRows，改变旧语义将导致历史命令不匹配；同源时间更改status也不满足既有additive升级。标准状态的版本化修复另列，不伪造source_updated_at、不回写历史Receipt。

验证：定向测试RED/GREEN；只读保存命令的候选数量；不重复商城查询。风险：仅状态合格不等于有库存、利润、内容质量、来源新鲜或获得执行权。回滚撤销新增源文件与测试即可，数据库无修改。
