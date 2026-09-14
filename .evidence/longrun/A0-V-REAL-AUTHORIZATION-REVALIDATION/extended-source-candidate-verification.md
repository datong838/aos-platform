# SC4-5e8 后四类源声明与三类快照

2026-09-14，基线5ff433d3；Lease A0-V-SC4-EXTENDED-SOURCE-CANDIDATE。

schema追加四类身份与结构，哈希绑定full-store-source-structure-20260914.json（6ef53e8f516137f95907c66caa919ed34190ef32606ef12af71f556fa7db2ca0），前八历史结构条目不改写时间。masking追加明确秘密/配置值/评价自由文本媒体/支付载荷排除。旧越界映射仍被拒绝；新增P09/P10/P11只读最小必要列并通过Canonical。

1.11.0源树f2bc7069f564af79dbef3feb14da9ba64a7b6fd767cef4a2879421caf71cb7f5不变，仅bundle/schema/masking/三映射/evals共7文件相对变化。P12原映射仍未通过完整源选择与订单归属，paymentSnapshotComplete=false；不能声称12/12。

先缺生成器4红测；实现后65 passed/7既有警告/6.08s，整包十一类合成对象通过。AR2 1909/187/93五数组空、memory validate与diff-check通过。配置值/评价正文能力未实现，不把元数据/评分当完整业务诊断。

真实只读聚合：小程序3条status1；配置37启用/1停用；评价5条显示且审核标志1，分数5。支付211条relate_id都命中同店订单，但out_trade_no仅181命中，这种不一致需要业务代码与原始关联口径解释；未读支付载荷或账户凭证、未写任何源或主数据。

SC4-5e8：后四类源结构/隐私声明及三类最小快照1.12.0完成，65项回归通过，十一类静态对象通过。新树7d0eaeb6c99da59f8e9f08f78607da60320f97bdaab881184c4f7e6a47fd9587；配置仅元数据、评价仅评分/关联键，敏感正文未读。支付211条relate命中但交易号仅181对应，仍未完成，下一查源业务事件/订单副交易号语义。静态11/12，主库仍先前2/12，完整补齐/首链未完成。
