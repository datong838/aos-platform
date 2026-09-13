# 路由 UI 接口实际部署与回读

2026-09-13，API 代码 959e4788。先受控 preflight GREEN（sourceCalls=0 / runsCreated=0 / productionWebIdentityComplete=false），核对旧 PID 30527 确为 c3e57bf9 产品 API 后 SIGTERM；随后以同一受控 profile 启动新 API18181。Host 和运行资源不重启。

真实 GET 结果见 runtime-workshop-ui-live-readback.json：health200；org-org/dev-project 目标安装97a... route=analyst 返回200，安装 ETag5 / ready / generation3a445... / epoch3 / binding4 / enabled true / fence false，ui=null；重复 route422；dev-org canary404。均只读。

IAB 重连当前已有5173资产页后点击“刷新安装状态”：当前安装 ready、enabled/ready、3/4；提示“当前安装没有可加载的前端扩展资源。”，目录“暂无可见工作台入口”；默认身份的登记读取仍明确拒绝。未点击写动作。

因此 API 接线与隔离已真实验证，但前端领域包和业务运行并未交付完成。下一波进入 current-ready 运行时目录的签名贡献投影及宿主渲染接点；随后新版本前端/bridge 构建、正式交付、经营首链与八场景观察。真实切换另待独立审批身份和正式动作定义，不能制造假审批。
