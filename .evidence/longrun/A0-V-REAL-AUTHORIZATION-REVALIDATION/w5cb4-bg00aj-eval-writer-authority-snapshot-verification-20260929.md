# W5CB4 BG-00aj｜同事务 Eval writer 当前 authority 预检验证

方案：`w5cb4-bg00aj-eval-writer-authority-snapshot-plan-20260929.md`。只新增 `aip_eval_writer_authority_preflight.py` 和专项测试，无路由、生产写入、migration、Host/worker/Provider 启动。运行前必须是同一 `aos_aip_eval_writer` 的 serializable 精确租户事务；读取 current root、Target/Judge identity、撤销及精确 Run，核来源/Owner/approval、证书与 Ed25519 Receipt、Report 全 case/独立 input hash，返回验证后的 proof，函数不 INSERT。调用方的正式同事务 INSERT 留 BG-00ak。

## 本次可复核结果

- RED：先写专项测试，`pytest .../test_aip_eval_writer_authority_preflight.py` 因目标模块缺失，collection 退出 2。最小实现后专项 10 passed；复审补 `Run.status=succeeded` 的门及测试，再跑专项 11 passed，退出 0。尝试 test-only 空 Owner UPDATE 被已有数据库约束拒绝，因此删除该无效负例；生产代码仍检查 Owner 非空。
- GREEN：test-only `aos_bg00ad_schema_v2_20260929@a0v114` 用真正 Ed25519 test-only 签名；正向、缺 authority、Target/issuer 撤销、错签、错 role/tenant/isolation、错 input、缺 case、未完成 Run 负例。相邻累计命令：`pytest -q` 对本波、BG00ai/ah/af/ad/ab、纯签名和当前预览 HTTP 测试共 57 passed，退出 0。`git diff --check` 与 `compileall` 退出 0。
- 事后独立只读连接：test-only 和当前 `aos_current_preview_20260927` 都为 `a0v_114`；六张 Eval authority/Receipt/Report/sidecar 表行数逐表均 0。当前 API `/v1/health`、`/v1/ready`、`/openapi.json` HTTP 200，Web `/aip/skill-publish` HTTP 200，18181 监听数 0。`/health` 是错误路径，返回 404；本次使用正式 `/v1/health` 验证。

## 复审与下一波

预检只证明 test-only 同事务读取和纯签名判定；还没有正式 issuer/Owner/approval、真实 G2 内容/S3、当前 DB 专属 writer ACL，也没有完整写入、Gate/Host/业务首链。当前数据库保持只读，Skill guard 不放行，dev-org 未写。BG-00ak 将预检与独立 connector、双 Receipt/Report/sidecar INSERT 组合为一个事务，并用故意失败验证全部回滚；当前正式实例的角色/ACL 切换仍须独立备份+克隆+零执行窗口门。
