# r2方案内的解码限额补记

主体仍为implementation-plan-r2.md，完整231Goal与全部边界/文件scope/计数/签名/原数据保护不变。reader首轮55/联合229/冻结481及原PG验证、独立reader code r1 PASS合法消费保留，尚未部署或Delivery。

补查复现：源JSON在单行字节限额以内也可能具有过深嵌套，Psycopg使用的JSON decoder可在fetchone期间、模型或隐私校验之前抛出RecursionError。新增专项以真实json.loads处理1100层合法JSON，已在当前reader上RED，证明该异常未映射原稳定限额错误。

按r2“载荷/解码/错误稳定拒绝”要求，仅在原read异常映射中增加RecursionError→CUSTOMER_CONTACT_READ_LIMIT_EXCEEDED，不改变成功路径、SQL、计数、签名或投影。原库与writer/Store/DDL/Web不动。新冻结r2与原w6_007/008独立tmpfs PG r2复验，增加真实PG JSONB深嵌套读取拒绝，然后fresh reader质量与route质量。旧r1 PASS只对应旧源，不作为新候选最终门，不将已通过481冒充新版本验证。
