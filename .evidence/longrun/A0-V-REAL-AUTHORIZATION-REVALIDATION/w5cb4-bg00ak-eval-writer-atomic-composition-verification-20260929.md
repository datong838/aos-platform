# W5CB4 BG-00ak｜隔离 Eval writer 原子证据登记验证

方案：`w5cb4-bg00ak-eval-writer-atomic-composition-plan-20260929.md`。先写真实独立登录 test-only 专项，目标模块不存在时 RED（collection 退出2）；最小实现后公开入口仅用 BG-00ah 受保护凭据文件和独立非特权 LOGIN。事务内先设 serializable/专属 role/精确租户，取数据库 `transaction_timestamp()` 作当前撤销 cutoff，再 BG-00aj 预检真 Ed25519/Owner/Run/Report 全 case，双 Receipt→Report→sidecar 同笔 INSERT；无 UPDATE/UPSERT/自动 retry/Gate 提升。

## 新鲜结果

- test-only `aos_bg00ad_schema_v2_20260929@a0v114`：独立 LOGIN 正向提交后读回 Receipt 2、Report 1、sidecar 1；故意先占 Report 唯一键时，写入入口失败且本次新 Receipt 0、sidecar 0；错签与缺配置在 INSERT 前失败。专项 4 passed，退出0。
- 复审发现公开入口接受旧 `evaluated_at` 可绕开当前撤销，于是改为同事务数据库时间，测试签名夹具只增加可选时间参数，既有默认用例不变；BG-00aj 预检另加 Report passed/failed/total/pass_rate 与 case 汇总一致性，负例覆盖。相邻累计 62 passed，退出0；`git diff --check`、Python `compileall` 退出0。
- 首次测试正向写入后，清理被 test-only append-only 触发器拒绝，专项当时退出1，留下精确测试行。先只读查明行数和用户触发器，随后仅在 test-only clone 的单事务内短暂 `DISABLE TRIGGER USER`、精确 DELETE、`ENABLE TRIGGER USER`，并撤销临时 GRANT/policy；失败会整笔 rollback。修正 fixture 后重跑专项及累计通过。最终独立只读连接确认：test-only 与当前 `aos_current_preview_20260927@a0v114` 的六张 Eval 表均0行；临时 policy 0、disabled user trigger 0、BG00ak 临时 LOGIN 0。当前库没有任何角色/ACL/业务行变动。
- 当前 API `/v1/health`、`/v1/ready`、`/openapi.json` 和 Web `/aip/skill-publish` 均 HTTP200，18181 监听0。此检查只证明服务存活与禁入状态，不证明经营链。

## 界限与后继

BG00ak 仅证明 test-only 独立身份、当前时间预检和证据原子持久机制。提交后网络断开仍可能形成 unknown，现无自动重发；下一波 BG-00al 应以只读精确 Receipt/Report/sidecar 对账封闭 unknown。当前正式 issuer/Owner/批准、writer ACL、G2 内容/S3、Gate/Host 和自然首链仍缺，Skill guard/Host/worker/Provider 不放行。正式实例授权或迁移必须另波备份+克隆全链+零执行窗口。
