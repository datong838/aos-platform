# E17-s3o-w-ao-b6｜原 ToolBinding 无来源 active 写 RED 与协议复审

## 前置

按同前缀方案先读 BIND-1、W-L20、当前签名来源 b5、原 Store/API/DTO/RegistryReceipt schema 和 s3o-r strict xfail；仅在 `services/aos-api/tests/aip/` 新增目标负例。pytest 的 `conftest.py` 建随机 `aos_test_*_ti4_test` 测试库，当前原命名卷未写。

| 门 | 命令/实测 |
| --- | --- |
| RED | `AOS_DOTENV_DISABLED=1 PYTHONPATH=../..:. uv run pytest -q tests/aip/test_e17_s3owaob6_tool_active_source_red.py`（API目录）exit1，1 failed：请求无正式 ToolDefinition，测试禁止打开 writer，但原 `AipAssigneeResolutionStore.upsert_tool_binding` 先调用普通 `_connect(scope)`；准确失败 `AssertionError: original owner writer opened without formal ToolDefinition`。 |
| 持久 RED | 将同一目标标成 `xfail(strict=True)`，与原 `test_e17_s3or_tool_binding_source_receipt_pg.py` 合跑 exit0、2 xfailed/7既有 warnings；`py_compile`、`git diff --check` exit0。这不是正式业务通过。 |
| 原协议复审 | `UpsertToolBindingRequest` 只有 binding/tool/version/agent/status/capability/policy，没有 signed ToolDefinition exact ref/安装 epoch；原 Store 用普通 `db.connect` 写 `aip_tool_binding`，无发行 Receipt；RegistryReceipt 表通用字段可容纳 operation/ref/hash，但当前普通 runtime 仍有表 INSERT 权，不满足防伪造 issuer。无来源时仅补 Receipt 会形成伪授权。 |
| 当前签名来源 | b5 当前四 signed bundle 无 ToolDefinition；3 Provider 插件只有 dev 批准，不能构造正式 Tool 源。当前库 ToolBinding0，未对原库执行写入。 |

## 结论和下一步

RED 证实 active 入口缺正式来源前置。现在不能仅把普通 owner 写事务附加 Receipt，也不能加入假 Tool ref 或 test-only 账号。全面禁用所有 active 虽能通过负例，却没有正式正向协议，且会使原正向/撤销回归失去目的；本波保留 strict xfail，不把它改称 GREEN。

下一波应先冻结**签名 ToolDefinition 精确来源、安装/租户/epoch、独立发行者和同事务 Receipt**的文件级合同，设计在不破坏 disabled 撤销和已有版本幂等的前提下的隔离正反验证。若正式来源仍缺，转其他已登记安全代码项，长期 Goal 保持 active。原库只读，Host/worker/Provider关；无 API/Web/页面改动，浏览器不适用。
