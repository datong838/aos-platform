# AU 陈旧健康实例正式退休验证

## 结果

AU installation `eddc89f9-1e91-4e42-be4e-7d81dc941c1d`、generation
`01a5eb0a-f41f-40f7-ba00-b5db23a7806f` 已通过原 RuntimeDisable Owner 正式退休。唯一 disable operation 为
`51bdbc84-901f-448d-87e8-5a655790e0d3`；请求非 replay，唯一 Runtime Host 已完成 fence/detach，执行器只读命中
终态并记录 `claimedByHost=true`、`resendDisable=false`，没有重复提交。

## 终态

- Binding rev9/epoch5：disabled、fenced、desired disabled、observed unknown；
- 九路回 legacy rev116/group143，三项资源全部 released；
- definition rev73 disabled，AU attempt=0；
- 十二 Run 仍 running，十二 Dataset Receipt 保留；Store Receipt、`ecom_link` 与 projection pending 均为零；
- running、unresolved、runtime pending、`dev-org/dev-project` canary 均为零；
- lifecycle 恰为一笔 operation、两张不可变 receipt，阶段 `fence → detach`；
- audit 返回 `AU_STALE_RETIREMENT_GREEN`，externalEffects=0。

## 验证

- guard 在写入前锁定 AU identity、Binding rev7/epoch4、extension rev114/group141、definition rev73 与零 attempt；
- request-disable 仅受理一次，expected binding revision=7；Host 完成后 process 阶段只读终态，未再次发送 disable；
- 专项与累计回归 `71 passed`；Python 编译、差异检查均在本提交前重新采集并通过；
- 方案与实现一致：不修改十二快照 Run/Dataset Receipt，不调用 `run_definition`，不读取商城源数据；
- 8434 仅作只读存活检查，18181 保持无监听，230 L0 继续挂起。

## 下一波

只能以本次 exact detach Receipt 作为父权威创建 AV direct successor。AV 先完成方案、安装、配置、登记、路由切换与
健康观察，definition 继续保持 rev73 disabled；未取得新的正式 authority 前，不启动 snapshot worker，也不产生 attempt。
