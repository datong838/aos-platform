# Runtime Workshop HTTP 接入验证

基线 03abc3dd。独立 GET /v1/runtime-workshop/modules，服务端主体决定 scope/roles/markings，响应 no-store。ControlPlane 与目录共享 RuntimeViewReader，无 lifespan 进程有惰性只读回退。未触发运行工作或对外副作用。

红测：路由模块不存在，收集失败。实现后 HTTP/RuntimeView 回归 34 passed；接线聚焦回归 9 passed、1 deselected。新测试另含构造不实例化 Loader。闭包 ar2-7 1834 模块/161 分类/93 迁移，五类错误为空；生成器 --check 与 diff --check 通过。

扩展检查诚实记录：原 test_control_wiring 的 importing_wiring 测试失败，其导入 aos_api 包会加载整个 main；本波次未修改或跳过其原始测试文件。旧 router manifest 测试仍使用 547 项和 4479 路由的封存断言，基线 HEAD 实际已有 548 项/4492 路由。本次不直接重写旧封存哈希。已用相同运行探针对比 HEAD 生成聚合与新聚合：4492→4493，仅新增该 GET，移除 0，重复集合不变（runtime-workshop-route-delta.json）。因此本次不能声明全量历史测试 GREEN。

当前为代码接入证据，未部署本提交，尚无真实 frontend。下一波继续前端独立目录消费者与失效卸载；新包资源和 bridge 业务能力仍待开发。业务总目标未完成，230 L0 继续挂起，不 push。
