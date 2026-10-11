# 恢复包core继任版本方案

只读实证：历史Registry的aos/domain.ecommerce.core@1.4.0 hash91bbe...与当前1.13四包构建core1.4.0 hash不一致，1.4.0/1.4.1/1.4.2均published。不得update/revoke旧版、改content_hash、删除Registry或原安装，使当前新版强行覆盖历史同coordinate。平台与operations当前签名hash一致，Growth1.13尚不存在。

下一已登记最小步骤：准备新core1.4.3 unsigned候选及独立恢复构建profile，保留当前源码及旧四包profile字节；变更仅新的coremetadata版本及必要selfref，backend source不改。新profile复用原Growth1.13 builder，仅选择新core1.4.3，平台1.23.0/Growth1.13.0/operations1.2.0保持。原Growth依赖>=1.4.0<2、平台>=1.2.0<2允许1.4.3，原不可变release不会变。

拟文件：bundles/candidates/ecommerce/domain.ecommerce.core/1.4.3/（全新目录，不能覆盖旧版）、scripts/prepare_ecommerce_qyh_recovery_core_candidate.py、scripts/build_ecommerce_qyh_recovery_candidates.py及专项tests。先补细化文件级合同与RED，原candidate baseline/treehash/metadata/selfref/backend全量比较，原profiles专项相邻回归，然后原隔离build/qualification/tamper验证；未允许签新包、publish/安装、正式库切换、权限、Host/Provider、商城或旧Run。签名/发布范围要逐门核授权。

不通过改name/version文本直接把旧签名当新签名，不通过缩减包组或用旧1.10资源取代最终1.13真实部署；当前页面仍1.11未恢复。此方案不证明新core发布或恢复完成。
