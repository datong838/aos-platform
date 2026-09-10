# 调用前价格权威联检验证

基线 37f141b8，m1 单写者；Task A0V-INVOKER-PRICE-REVALIDATION。

先添加 missing/binding/hash/tenant/inactive/future/expired 七项负例，旧实现全部 DID NOT RAISE，复现了错误价格配置仍进入模拟 transport 的缺口。修复后新增不可读取价格和真实治理 Owner 授权不匹配路径，均在 Secret/transport 前拒绝。

五个相关测试文件合计 88 passed，7 warnings；包括原文本/图片调用、开发范围判定、合同兼容、exact 价格与当前预算策略授权联检。使用 AOS_DOTENV_DISABLED=1 与 AOS_TEST_USE_SHARED_DATABASE=1，无 dotenv 读取，无数据库写入、无真实 Provider 请求。git diff --check 通过。

原有七项 schema/deprecation warnings 和退出时 JDBC logger closed stream 仍存在，不作为本切片已修复项。测试完成 exit_code=0。

实现与方案对账：调用器独立回读 selectedPriceSnapshot，匹配模型价格 ref、ID/revision/hash、租户、active 和当前时效；治理 Owner 要求 deferred 价格的授权与当前 exact BudgetPolicy 一致，再检查模型及批准范围。旧已知价格不改变正文/hash。发布与 Resolver 联检仍未接入，deferred ACTIVE 合同禁入继续保留。本次不是 A0-V 或真实业务首链完成证据。

下一施工入口：将相同联检接到模型发布和 Resolver，再完成 pending-cost 的业务结果承接；之后才能登记真实 active 模型/路由、运行栖月汇首链。媒体慢响应遵循延长等待、先查已提交任务、仅安全失败重试，不以单次成功推断恢复/幂等已完成。
