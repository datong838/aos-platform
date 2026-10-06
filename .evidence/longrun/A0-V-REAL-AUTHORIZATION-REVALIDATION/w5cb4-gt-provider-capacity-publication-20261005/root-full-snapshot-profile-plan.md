# 完整根快照原生结构门

基线2c8b6fb9 / AOS-001407，原publication Task/Lease有效，本thread m1唯一写者。复习231、原root registration、storage实测及identifier方案。候选一：完整非授权snapshot纯计算profile（本轮）；候选二：正式152根登记/部署anchor/bootstrap授权/epoch和Source完整COMMIT，迁移scope另登，不冒用已占151。

新增独立read_root_snapshot(bytea)与read_root_time_literal(text)，复用原read_root_identifier_literal而非容量200printable/read_signed_body。ASCII8MiB/恰trustRoots、0..10000完整根；原紧凑canonical全体原文逐字节对比。数组json_array_elements保持opaque root，不PG对象提取。完整每根严格固定sort_keys字段顺序8字段，以JSON string literal词法捕获标识；algorithm Ed25519、公钥标准32bytes base64、revision sha256lower64、时窗starts<ends和revokedAt nullable，不加366日/撤回窗口等原文件没有的门。所有标识由原整数codepoint校验，完整(pub,key)严格递增，重复/倒序拒；规范string literal消除不同转义等价身份。空原snapshot合法，不能借空root获得授权。

时间接受原freeze的datetime.isoformat归一输出：YYYY-MM-DDTHH:mm:ss[.6非零micro]±HH:mm[:ss[.6非零micro]]，合法Python localyear1..9999/month/day/hh<=23/mmss<=59，offset绝对值<24h，秒/微秒offset保留，零offset只能+00:00。make_timestamp构造local后固定UTC减精确offset interval得到timestamptz，允许UTC落BC/year10000以保原极限localyear，不用会溢出的Python UTC归一。Python File fromisoformat对小于1秒纯offset归一UTC，transport无该形式，必须以原freeze对照决定拒绝/归一。日期公钥在transport规范化前可接受原Z/comma/base64非标准padbits，不把原文件输入canonical要求误套输出。

返回每根完整opaque原文bytes、两个身份literal/codepoints、公钥bytes、revision及三时间（非trust/非登记），所有行通过后才返回，出错整个SQL失败；SQL INVOKER/IMMUTABLE/search_path pg_catalog/PUBLIC无EXECUTE。输入bytes不认caller verified/hash；整体hash必须由外部签名bootstrap+独立固定部署anchor对照后才登记。正式登记不可截取子集、自由callerkey或自签trust。

文件aip_provider_capacity_publication_store.py、test_provider_capacity_publication_pg.py及本目录（原scope）。先缺入口RED，测试原安全File真实1001全根（240/孤立surrogate/quotedkey/秒microoffset/极限date/撤回及全字段）原SQL逐项对照，空/数量上界/超过2MiB及8MiB门、合法长根期限、base64、时间/字段/排序/重复/ASCIIcanonical/NULLshape负门和实际role拒绝；专项+相邻、AST/diff/精确hash/提交/Authority同步。无生产schema安装或真库，不改原File或签名文档profile，完整Task不Delivery。

首green失败：新正则误将revokedAt排列在revision之前，与原sort_keys输出不符。单根隔离诊断已定位regex shape拒绝；纠正原字段顺序及capture索引，不改原transport，不放宽字段未知/顺序门，失败日志保留。

## 大输入诊断与测试输入路径纠正

新增完整专项r4中10000根内联SQL常量实际backend被signal9终止，固定256MiB容器记录OOMKilled，Postgres自动恢复；后续49测试完成。不能把偶发r3通过当内存稳定。保留r4失败及memory diagnostic，未更改镜像/内存/生产库。相同10000及10001根/8MiB越界，改同事务TEMP bytea输入列再LATERAL函数（减少巨型内联常量查询驻留，模拟后继不可变原文表输入），不改生产parser或上界，专项1/17.91s通过，采样85.98MiB、结束27.06MiB。这证明存储输入路径可用，不证明所有内联调用的内存根因已彻底归因。正式登记必须读取原文表值或受控输入策略，不暴露自由内联巨型SQL；后继8MiB接近上界再独立验证。TEMP数据/DDL在原fixture事务rollback，无持久root注册。

## 最终复审与证据

118行独立SQL包含时间与全snapshot两函数，完整8字段pattern纠正revision先于revokedAt，规范身份array排序/重复判定保留原域。全部返回仅untrusted shape rows；PLpgSQL set完全materialize后才交付，LIMIT1的末项非法反例拒绝整次。单根regexpr错误与OOM均记录，不改原File/旧profile或实际角色配置。Python归一原Z/comma/ISOweek/短offset/纯subsecondoffset→UTC与SQL微秒整数精确比对；BC/year10000 UTC瞬时值从合法localyear安全支持。revokedAt早于根窗口原File允许，本次不增加门。

大输入内联/巨型INSERT HEX SQL驻留触发固定256MiB cgroup中backend/client被杀；新输入工具仅测试内改为32KiB chunks COPY→TEMPhex parts按n拼接→TEMPbytea，整sha256独立DB与Python比对后再完整一次解析，未截根或分批解析，临时数据原事务rollback。近上界首fixture大小计算7290016未达7MiB断言失败，改85DEL后8190016bytes（<8388608，10000唯一根）bigHEX客户端137失败；分块COPY后target1/20.47s通过。没有删除原失败日志、增内存或更换镜像。内联SQL调用内存风险保留为正式注册输入路径约束与后继观察，未证所有客户端用法稳定。

专项最终50/28.31s（近上界加入前）；近上界1/20.47s；加入COPY整hash最后同一版publication+原signature相邻478passed/7warnings/71.46s全部terminal0。两文件AST/精确whitespace与方案自洽复核通过；无界内存arrayconcat避免（SQL有序string_agg），COUNT10000/10001与8MiB越界/空原集合均覆盖。原File输入1MiB与输出8MiB分别执行/明确，不将纯parser10000上界试验冒充原File成功授权。正式snapshot/root登记、外部anchor/bootstrap、身份/权限/epoch、Source实际最终COMMIT和consumer仍未通过；本轮无当前真库/Host/worker/真实Provider/浏览器变更或fullTask Delivery。

下一已登记方向：注册所用root identity不能存PostgreSQL decoded text/surrogate。应由完整已校验snapshot派生canonical ASCII literal及integer codepoints身份键，原bytes与整hash不可变关联；实际private role/owner/tenant和root-policy epoch协调，可信anchor/bootstrap完整绑定后允许root登记。新增152migration须单独Task/Lease核完整重叠scope后创建，不覆盖已占151；旧issuer不得获得root写权限。剩余 Source最后COMMIT TTL门继续保留，不由root/模型通过授予业务执行。
