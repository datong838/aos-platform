# W5CB4 BG-00n｜受控 Eval 对象字节门验证

基线 `m1@573eff9b`、权威 `AOS-000862`；方案见 `w5cb4-bg00n-eval-content-readback-plan-20260929.md`。当前签名增长包 G2 Evals `BLOCKED`，另一个 `w03-l05-dry-run-cases.json` 是 D3 测试矩阵，未充作 D01。当前 9000 无监听，无正式 G2 Eval 对象；本波没有改 Dataset 登记、真实库或 Bundle。

## RED 与实现

- RED `pytest -q tests/aip/test_aip_eval_object_reader.py tests/test_object_store.py -k 'eval_object_reader or aws4_request_bounds_get_response' --tb=short`：退出 2，新 reader 模块缺失。单跑 S3 上限测试：退出 1，`_aws4_request` 不接受 `max_response_bytes`。HTTPError 读取上限补充 RED：退出 1，实际 `read(-1)`，期望 `read(200)`。
- 新 `aip_eval_object_reader.read_verified_eval_object` 只接受 `org/project/evals/` 下无空、点、转义或特殊字符段的 key；默认经 `object_store.get_bytes(max_bytes=2MiB)` 读取，要求非空 bytes、大小不超上限且 SHA-256 等于 exact digest，错误只返回固定失败码/短信息，不记录字节。
- `object_store.get_bytes` 增可选上限，底层 HTTP 只取上限+1 字节；默认无上限的旧调用保持原行为。HTTP 错误正文最多读 200 字节。没有新增写请求或凭证暴露。

## 新鲜验证与边界

- 初次专项 GREEN 为 `8 passed, 4 deselected`；新增默认 S3 调用及错误正文用例后，最终 `test_aip_eval_object_reader.py test_object_store.py`：退出 0，`13 passed, 1 skipped`。跳过项是需 `AOS_S3_LIVE=1` 的真实 MinIO 往返，当前没有可用 9000 存储。
- 最终重跑 Eval/Release/Skill Publication、内容评审与对象存储相邻：退出 0，`65 passed, 1 skipped, 2 deselected`；两项 deselected 是同一函数的 ACCEPT/RETURN，上一波 ACCEPT 单跑已 GREEN，RETURN 的正式权限来源仍 RED。本波没有改该路径。
- `python -m compileall -q` 四文件与 `git diff --check` 退出 0；纯后端未改页面，浏览器验收不适用。测试注入隔离字节验证代码逻辑，不是正式对象存储或业务来源验收。

复审：该 reader 尚未接 `AipEvalAuthorityStore`；即便接入，字节 hash 仍不证明内容格式、字段 allowlist、case count、脱敏签发 Owner/撤销、Judge/Target executor。下一波先冻结 G2 Eval 正式内容格式与签发合同，并在隔离对象存储做真实读回后，才能设计同事务 Dataset 接线。当前 D01、Skill 发布/Binding、Host/worker/Provider 与自然首链继续禁入。
