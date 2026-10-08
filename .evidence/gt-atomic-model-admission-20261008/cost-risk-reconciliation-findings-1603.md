# 原始费用基准核对结论

在原保留 PG159 fixture 的两个独立 SERIALIZABLE READ ONLY 连接中读取，核对精确 manifest 价格引用与原 proposal 正文哈希，之后独立累计账本不变。

Target 与 Judge 均为 deferred 价格，input/output/cached 数值价格全为空；实际金额未知，不是零费用。两侧 proposal 均为 perRequestRiskMinor10 / totalRiskMinor100 / maxRequests10。Target 三账本0；Judge普通0、Eval0、Judge1行10分；原历史 Judge 风险预留保留，不释放、不删除。

现有 shared_risk_totals 数量是三种 reservation parent 的行数。没有证据把 maxRequests 自动解释为逐个 Provider 网络调用的计数。原 Manifest 每腿1分为 synthetic 描述，未有真实 held allocation；禁止把申请10分改称逐调用价格，或为两case擅自增加额度。

后续原子 allocation 实施须 server 推导每腿批准风险分配并原生验证并发累计≤精确 parent 上界，补齐 call/Intent/Source/actual Usage 与不可绕过 finalize；deferred Usage 可以计量tokens，金额仍null，不能制造报价或已结算记录。现有授权不扩展，完整业务/五父Task保持未完成。

调查脚本初次把 VersionedAssetRef 当成 ResourceRef 导致 KeyError，读取事务回滚；修正后 Decimal 输出失败，完整只读查询成功但 JSON 不完整，该 partial 单独保留。第三次完成，第四次加入独立连接事后对账并完成。均无库写入/真实调用/迁移/服务重启。只为本调查添加脚本，不改业务代码；本次不涉及页面，不运行无关浏览器验收。
