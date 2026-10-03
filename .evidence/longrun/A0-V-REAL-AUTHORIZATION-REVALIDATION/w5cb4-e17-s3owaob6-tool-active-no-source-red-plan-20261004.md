# E17-s3o-w-ao-b6｜原 ToolBinding active 无正式来源 RED 方案

## 合同与现状

复习 231 主计划、BIND-1 31、W-L20 原 Store/API、D-wave s3o-r/s3o-w-m 和 b5 当前签名来源核验：四份当前签名 bundle 均无 durable ToolDefinition；正租户 ToolBinding0。原 `upsert_tool_binding` 在 active Agent 后直接用普通连接写 ToolBinding，不同事务 RegistryReceipt 的 strict xfail 已登记。正式正向需精确签名 ToolDefinition、专用非 owner issuer、幂等同事务 Receipt；不能以普通 owner 或内存 tool 名代替。

## 文件级步骤

1. 仅在 `services/aos-api/tests/aip/` 添加原 active 路径 RED：没有正式签名 ToolDefinition 与发行 Receipt/issuer 时，请求不得触发 DB 写，也不能留下 active binding；以独立的 disabled 旧绑定撤销测试保护已存在路径。先运行 RED 与旧 strict xfail/相邻原测试，逐项记录实际影响。
2. 复审 `aip_assignee_resolution_store.py`、`routers/aip_assignee_authority.py`、`aip_assignee_resolution.py`、Receipt schema、签名 bundle 合同，确认是否能在不新增未批准公共字段/假来源的情况下最小实现。若必须改变正式 ToolDefinition/Receipt 公共协议，先完善方案和隔离正反证明，不因 RED 直接做 blanket 禁用或伪造来源。
3. 实现后专项/累计回归、方案/代码/权限复审；当前真库只读，正式切换另需备份/克隆/零执行窗口。此切片最多证明禁入，完整正式发行正向仍必须另门验证。

本波不读商城源、不重放旧12 Run、不手工 Run、不启 Host/worker/Provider、不写当前库、不 push。
