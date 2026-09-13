# 首次登记来源核验

2026-09-13T09:19:54.094493+08:00，基线b755579c，m1串行。

新增aos_api/ecommerce_growth_registration_origin.py及tests/extension_runtime/test_ecommerce_growth_registration_origin.py。固定ReceiptRef为FirstDispatchRegistrationReceipt/canonical UUID/revision1/sha256，严格extra forbid与bool整数拒绝。复用decode_registration_receipt检验存储scope/body/hash；匹配exact ref、当前排序九项snapshot、安装/generation/epoch/bindingRevision，返回独立原登记请求供后续当前权限/配置/签名核验。该纯组件不能确认数据库新鲜性，也不授予执行权。

RED为组件不存在的导入失败；实现后59项原始契约/回执/来源测试通过，4.85秒，8项既有框架及unsafe_construct负例序列化警告。覆盖假ref、scope、目标和版本漂移、bool伪整数、部分/额外/混合/无序快照以及fence/revision变化；输入不变。AR2清册1819/158/93、五类错误为空；diff-check通过。

未接入Cutover，未更改主库、HTTP或签名包。下一波加入可选exact registrationReceiptRef并保持无ref旧请求摘要兼容；prepare/approval/Receipt重构绑定ref，当前安装/配置/签名核验必须同事务；commit/rollback沿exact快照并保留初始fence=true。不可任意允许fenced起点。未激活撤销和主库部署仍待实现。
