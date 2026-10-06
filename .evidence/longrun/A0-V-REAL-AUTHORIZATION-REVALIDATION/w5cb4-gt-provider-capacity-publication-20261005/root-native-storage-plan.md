# 完整根快照原生存储与提取选型验收

基线m1 f8a097a2 / AOS-001405；原publication Task ACTIVE、owner本thread、Lease20:00。复习231、原publication plan、root registration合同及完整transport。候选一：实际PG完整opaque json提取验证（本轮）；候选二：正式152登记/可信anchor/角色与epoch，需要独立migration scope及完整入口负门，后续推进。

不能把含原File合法孤立surrogate的完整ASCII快照转jsonb，不能截根或用子集hash替整体hash。本轮真实原FileProvider freeze全部1001根，包括孤立surrogate、内部空格、240字符及带秒偏移；同固定隔离PG纯计算transaction读取原bytes(bytea)整体sha256、json_array_elements完整count/ordinality和每根8字段原json文本。读取所有root原文不解码publisher/keyId，通过ASCII JSON literal精确比对；选取普通root才解码合法字段。对同文档whole jsonb转换、surrogate root ->>抽取分别实际拒绝，确认限制来自字符转换而非root数量。空库新卷不替真实库，现有测试none-network容器与固定镜像复用，每例rollback，不创建持久注册表或grant。

范围：test_provider_capacity_publication_pg.py及本目录。先实际PG实验保留输出，再固化可重复测试；这是选型证据，不是生产缺陷修复，不制造入口缺失RED。专项及publication/原signature相邻，精确hash复审提交后同步Authority/AOS/Prime。成功仅确定bytea原文+opaque json派生的可行性；完整root typed验证、规范顺序/重复身份、受控anchor/bootstrap整hash绑定、实际部署/身份、private登记role/epoch、Source最终COMMIT及consumer均未由此通过。

## 实测选型纠正

首探针SELECT json_array_length(whole->trustRoots)失败；独立对照证明whole ::json::text成功、array json_array_elements成功，但对象 ->/json_each/json_object_keys也拒绝合法孤立surrogate。不是只有jsonb/text解码失败，不能按初猜实现对象提取。保留七个实际SQL正负结果root-native-json-probe.json。

冻结后的独立transport恰ASCII紧凑{"trustRoots":array}，已知固定prefix和suffix的结构边界可以byte切片取完整array，再json_array_elements WITH ORDINALITY保留每根opaque原文。只对已取得的普通root做jsonb转换，异常root仅原文保留不得悄然过滤。测试逐项比对全部1001根原文和整体sha256，并证明所有三类对象字段提取与jsonb失败。此路径尚非完整任意caller输入validator：prefix/整体canonical/8MiB/重复身份/全字段接受域均正式入口独立校验；本轮不新增不完整生产parser。
