# 独立完整root标识ASCII原生校验

基线7b3ab914 / AOS-001406，原publication Task/owner/Lease有效。候选一：独立root identity canonical ASCII profile；候选二：完整snapshot8字段/时间/排序与正式152登记，需要后继完整方案及迁移scope。选第一项，是正式全root登记解析的必要部分，不另建替代业务目标。

复习231 A1首链/A2八场景、root-native-storage-plan、root登记合同及原File _is_exact_identifier：原配置允许240 Unicode字符、内部空格/control/孤立surrogate，拒空串/首尾Python strip空白/NUL。容量签名文档200 printable不可套用。PG对象解析会解码surrogate失败，因此单独扫描ASCII JSON string literal，返回整数codepoint数组（保留孤立surrogate，合法代理pair合并为一个Unicode字符）。禁止chr(surrogate)/整literal::jsonb；整数数组可在后继canonical身份唯一/排序与精确literal匹配使用，不获得trustedkey。

新增CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL及private read_root_identifier_literal(text)；SECURITY INVOKER/IMMUTABLE/search_path=pg_catalog/PUBLIC撤EXECUTE，纯计算无表/授权/来源。输入两端双引号、ASCIIcanonical JSON literal，最大2882bytes；遍历最多240 codepoints，短escape只quote/backslash/b/t/n/f/r，unicode escape四lowerhex；ASCII printable须literal，DEL及非ASCII/surrogate必须u转义，控制字符短形式按Python ensure_ascii规范，u0000始终拒。paired high/low合并；unpaired保持原合法码点。首尾空白表按Python str.strip全部Unicode集合固定，并与本机原接口逐项对照，不依赖PG trim或Unicodecollation。

文件aip_provider_capacity_publication_store.py、test_provider_capacity_publication_pg.py及本证据目录。先缺常量RED，再最小SQL；真实FileProvider原accepted identity完整对照，240 emoji边界/孤立及混合surrogate/ASCII escape/内部control/空白、全部strip空白前后拒、241/NUL/非canonical表示/畸形escape/NULL/shape，以及全ASCII0..127/固定种子Unicode批次，PG真实整数数组与原Python字符串ord一致。验证catalog/ACL，专项和publication+原signature相邻/AST/diff/一致性复审；无browser变化，不实际安装DDL或真库。后继完整snapshot/时间/公钥/排序/数量与整hash/受控rootanchor/bootstrap/实际roleepoch/SourceCOMMIT/currentconsumer仍待，不以本helper退出fullTask。

## 实现与复审

独立private SQL函数80行，以最多240整数codepoints的扫描实现，不构造PG surrogate text或解析jsonb。实际原安全File快照中的标识逐项对照覆盖全部ASCII非NUL内部字符、随机Unicode、极限emoji长度、孤立/重复surrogate、quote/backslash；规范代理pair合并为原File JSON解码后的一个字符。Python全0..0x10ffff isspace集合与固定29码点完全对账，首尾两向拒绝；不能套签名文档identifier。输入上界2882为240个SMP字符每12ASCII字符+双引号，非ASCII原literal与畸形/非canonical转义拒绝。普通NOLOGIN testrole仅获schemausage后仍EXECUTE拒绝；函数IMMUTABLE/INVOKER/search_path/PUBLIC ACL真实catalog审计成立，全事务rollback。

缺常量RED1/6.37s；首green1/5.57s；补矩阵62/10.85s；最终专项63/11.29s，publication+原signature相邻427/30.43s，7既有warnings，均原隔离目标。两文件AST及精确diff通过。无旧文件identifier门更改，无生产role/schema/grant、真库、Provider或自然首链操作。完整snapshot8字段/date/base64规范化、规范排序/整hash/trustedanchor/bootstrap、实际roleepoch与最终SourceCOMMIT未完成；原Task保持ACTIVE，不伪造fullDelivery。
