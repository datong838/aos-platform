# AS 失败实例正式退休验证

## 结果

AS installation `5d0a6d5a-4024-430f-831b-2af15b5ca889`、generation
`4cc2dc84-a452-4bac-aa56-0b1519a9826a` 已经正式退休。唯一 disable operation 为
`410d2bcd-3c56-4ea5-af0f-e599a08bc1ba`；请求 receipt 非 replay，Host 完成 fence/detach，执行器读回终态后记录
`resendDisable=false`，未重复提交。

## 终态

- Binding rev8/epoch4：disabled、fenced、desired disabled、observed unknown；
- 九路回 legacy rev110/group137；三项资源全部 released；
- definition rev70 disabled；唯一 failed attempt rev5 与终态原因保持；
- 十二 Run 仍 running，十二 Dataset Receipt 保留；Store Receipt、links 与 projection pending 均为零；
- running、unresolved、runtime pending、`dev-org/dev-project` canary 均为零；
- lifecycle 恰为一笔 operation、两张 receipt，阶段 `fence → detach`。

## 验证

- AS retirement/guard/saved recovery 专项与 recoverable Store/lease 累计回归：67 passed；
- Python 编译和差异检查通过；
- 8434 浏览器仍显示缓存本体、aos-api 不可达、写队列 0；未执行页面写操作；
- 方案与代码一致：固定唯一失败 attempt，先读回 accepted/terminal，再由正式 Owner/consumer 处理；不修改快照 Run，
  不调用 `run_definition`，未知结果不重发。

## 下一波

以本次 exact detach Receipt 为唯一父权威创建 AT direct successor，先完成安装、配置、登记、路由切换和长续租观察；
definition 保持 rev70 disabled。后续保存快照阶段使用关闭 qcursor/snapshot worker 的纯 HTTP profile，直到明确进入自然领取波次。
