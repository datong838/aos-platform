# Judge checkpoint 证据索引修复方案

Rules：AGENTS、AOS工程交付、231、原Task3合同。AOS-001703/m1 18093f116，原owner和有效Lease。

实际RED：原观察器拒绝checkpoint的35项evidence_files（上限32），尚未形成进展结论。只修改本Task目录checkpoint.json，新增本方案、reboot-checkpoint-history-index.json和reboot-checkpoint-index-verification.json。历史35份证据文件全部原样保留，索引逐项绑定原精确路径、字节长度、SHA256。checkpoint绑定索引、当前三份重启验收材料及本方案；code_files、Task原baseline、authority、owner、repo、thread不变。观察器32项门不改，索引不代替历史内容验收、不宣称业务完成。

验证：确认历史文件哈希和字节不变、无重复路径、原Task/Lease精确一致及有效；原观察器同一heartbeat重试通过。旧命令仅本地读取失败、未运行业务或数据库操作，可安全重试。无产品代码/正式库变化，不新增Delivery。
