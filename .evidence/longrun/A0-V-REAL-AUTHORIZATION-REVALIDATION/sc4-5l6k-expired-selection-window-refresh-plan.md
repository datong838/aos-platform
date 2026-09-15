# SC4-5l6k P02 过期授权窗口安全恢复方案

日期：2026-09-15  
基线：`71eb3ee0`

## 已证实故障

首次 E execute intent 在 2026-09-15 20:06 +08:00 发起。其 SourceSelection draft 的 `expiresAt=2026-09-15T11:52:34.162418Z`，实际执行已超时，因此 current guard 在创建 Run 前抛出 PermissionError，HTTP 返回 403。后置只读观察确认 Schedule=false，最新 Run 仍是历史 D Run `scr-f22003e66e544ebe`，E 新 Run、新 claim、新 ingress 均为零。

## 恢复规则

1. 旧 E prepare/selection/control/binding/execute intent 全部保留，不覆盖、不冒充执行成功。
2. 使用独立 `p02-e-first-chain-r2` 私有目录和 `v2` 幂等键；r2 selection、control、binding 必须逐级携带 r1 latest exact previousRef，形成追加历史。
3. r2 prepare 重新从 E current head 和 1.23 签名资产生成时间窗；生成后连续完成 selection/control/binding/execute，避免再次人为耗尽窗口。
4. bind 前数据库 latest binding 必须与 r1 binding-result 精确相等；否则停止，禁止跨过未知并发写者。
5. HTTPError 只解析 JSON 中安全的 `code`，异常文本固定为状态码和 code；不记录响应头、认证 token 或任意服务端正文。
6. r2 execute 前仍要求 Schedule disabled、最新 binding/control exact；finally 恢复 disabled。若 r2 进入执行器后失败或未知，不再触发第三次。
7. 正租户与 canary、单源调用、无商城写和 230 L0 边界不变。

## 文件范围与 preHash

修改：

- `scripts/a0v_qyh_current_product_event_first_chain.py`：`e95da497189672a10758c08263f680be4f81b070d4454f76c9d1b31d289262f2`
- `services/aos-api/tests/extension_runtime/test_a0v_qyh_current_product_event_first_chain.py`：`da2694a0124b3f9a96e4e3f4c63344c6492cdc880e89fb0c6a6699f35c0fd3ab`

新增本方案与后续失败/恢复验证文档。其他生产实现不改。

## 退出条件

- r1 403 被证明发生在 Run claim 前，且 Schedule 已回关。
- r2 三类 previousRef 逐级 exact，测试覆盖缺失/漂移拒绝。
- 安全错误码保留测试通过。
- r2 若成功进入执行器，只产生一个新 Run；随后按主方案检查 Dataset 和 ProductEvent。
