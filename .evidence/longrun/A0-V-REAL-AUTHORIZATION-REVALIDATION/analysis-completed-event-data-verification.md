# SC4-5c2b 完成事件数据需求

2026-09-14，基线49499adc；m1，不push。

AnalysisDataRequirementPreparation新增run_completed，走已完成事件的当前来源上下文。原claimed路径保留；两路径共用数据意图校验/实际对象读取/同安装sealed data Host及回读，幂等键都来自原dispatch attempt，不因完成事件产生第二份需求。

continuation上下文补出经完成记录验证的originalIdempotencyKey及当前analysis dispatch；不接收调用方任意指定key/分派。原首装、来源和运行边界保持。

红：完成事件无run_completed入口。绿：完成后首次需求、完成前已有需求后重试均得到同一实际数据需求；完成后旧Claim入口拒绝。累计34 passed/7既有警告/26.26s，AR2 1906/185/93错误数组全空，memory GREEN 1101/1084/2701，diff check通过。

隔离PG/明确来源和能力fixture，数据政策仍显式测试输入；不是主租户自动经营链完成。下一专用当前恢复门，继而安装内数据政策、真实补齐和已存在D01/D02/D03 Worker接入。通用bootstrap恢复仍拒绝，主安装未更新。
