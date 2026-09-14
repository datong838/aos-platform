# SC4-5f2 支付源字符串键修复与真实整组重验

2026-09-14，基线e389bba2；Lease A0-V-SC4-PAYMENT-STRING-KEY。

真实relate_id为str，v3新增可选positive_integer_strings：严格ASCII正整数、无前导零/空白/符号，最大signed64，保留字符串不强转。旧未声明映射行为不变。1.14.0 P12声明真实string并启用严格键验证；旧1.13.0与失败证据不变。

源树07478676ef5be20e10d185fe98113932a16a0b41d973248729285eaf4879015b保持，相对仅bundle/p12/evals三文件变化；独立新评估器用字符串关联键，原评估器不改写历史。初始13项新规则红测，修复后三版122 passed/5.92s；候选59 passed/5.73s；均7既有警告。十二类静态评估通过；AR2 1910/187/93五数组空，diff-check通过。

真实整组重验2026-09-14T08:09:29.496327Z至08:09:31.013772Z：全部12表InnoDB，同一私有REPEATABLE READ只读事务，892条均规范通过。Shop1/Product65/SKU73/Category11/Order185/OrderLine235/Shipment19/CustomerLite54/Weapp3/Config38/Review5/普通Payment203。源行不落盘，只存数量/哈希/结果于real-snapshot-group-20260914-payment-key-fixed.json。links全0，mainObjectsWritten=false，formalFulfillment=false；不能把这次开发验证当正式关系或主安装完成。

SC4-5f2：relate_id真实字符串类型修复完成，v3规范正整数字符串校验；122项三版回归/59项候选回归通过。1.14.0树9cb6cd266571dfbe7725e3411229f307025beec6ea93380a995529aa610d4b76。真实同事务十二类892条全部规范转换通过（含203普通支付），约1.52秒；仅开发者只读验证，主落库/关系/Fulfillment仍未完成。下一完整集合的关系/窗口与正式Owner回执绑定，再Outbox恢复和八场景。
