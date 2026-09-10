# 真实文本样本结果

基线 ef0a189b。固定模型 agnes-2.5-flash、Provider@1、Network@1，三个公开合成样本均通过精确文本合同。

| 样本 | token | 延时毫秒 | 判定 |
| --- | ---: | ---: | --- |
| instruction | 62 | 484 | 精确通过 |
| source | 82 | 670 | 精确通过 |
| missing | 76 | 342 | 精确通过 |

总计 3 次真实调用、220 token；无数据库写入。结果为 a0-v-exact-text-live-result.json，重放 a0-v-exact-text-live-replay.json：providerCalls=0、所有样本 metadata 完全相同。另用临时目录验证首次排他占位、未决拒发、完成回读、身份漂移拒绝和 0600 权限，全部通过。

首次执行导入间接触发旧 main dotenv 加载，日志混入 stdout；没有在证据输出密钥或响应正文，但存在不符合禁止凭据入环境的实现缺口。执行器已显式禁用 dotenv；新增独立 output 参数，避免日志混入 JSON。首轮 JSON 从原 stdout 中提取原始结果对象，未修改测量值；重放没有新调用。

本证据只证明三个固定样本可执行，不证明复杂分析质量、商业计费、图片/视频能力或真实经营首链。未发布模型 Eval Gate 或健康观察；下一步将固定样本证据接入正式 Eval 权威，补开发未核价执行合同与 Model/Route 正式接线。
