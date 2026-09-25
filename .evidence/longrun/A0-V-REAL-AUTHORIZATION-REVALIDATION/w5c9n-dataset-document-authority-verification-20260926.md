# W5c9n｜Dataset 不可达 GET 文档去重验证收口

## 方案、RED/GREEN 与安全边界

方案 `m1@4236d78b`，测试夹具补订 `m1@44bfd1f4`。只改 `services/aos-api/aos_api/routers/phase5_datasets.py` 两个后置 GET decorator 的 `include_in_schema=False` 及顶部事实注释；新增 `services/aos-api/tests/test_w5c9n_dataset_openapi_authority.py`。endpoint/路径/注册顺序/鉴权/POST 和其它 Dataset API 未改。

- 初始 RED `1 failed` 于预期后置 GET 仍公开，但默认 pytest autouse 夹具意外在**专用 test VM 127.0.0.1:5433** 建/迁一次性 `aos_test_*` DB。立即暂停、复核 `conftest.py` 的 finally drop，专用容器数据库残留 0、真实 recovery PG 独立；后续加 `--noconftest`，无再迁库。第二次无夹具 RED 仍 `1 failed` 于 `[True, True]`。
- 最小修改后专项 `1 passed, 16 warnings`；最终注释补齐后重新跑仍 `1 passed, 16 warnings in 12.42s`。测试锁住两个后置 GET 仍注册但不进 schema、前置 `wave_ext` 可达 GET 的 schema tags、原 Dataset POST 与后置 preview 文档仍存在；未调用业务 handler。
- 受影响累计精确选择路由捕获/同形冻结两项及 manifest 静态计数：`3 passed, 1 failed in 102.72s`。唯一失败 `test_manifest_count_order_domains_and_unique_keys` 硬编码 547，但现有 manifest 550；本波未修改 manifest/generator，故为存量基线漂移，不能说累计全绿。不得直接把断言改成 550 而不核 domain/order/唯一键。下一波 W5c9o 先方案审这个独立缺口。
- `py_compile`、`git diff --check` 通过；专用 test VM `aos_test_*` 残留 0。业务 8080 离线，纯 HTTP 18181 运行进程未重载新代码，本波不是线上生效/浏览器 GREEN。

## 九步/退出

1. 复习 231、W5c9l/m 与既有路由优先测试；2. 方案和补订先于代码；3. RED；4. 两 decorator 最小改动；5. 专项 GREEN、累计 3/4 并显式保留存量失败；6. 代码/方案一致性和写端点未激活复审；7. 8080 离线未冒充浏览器验收；8. 本 verification/代码提交、D-waves/AOS CAS/Prime；9. W5c9o 先审 547→550 manifest 基线并做兼容测试，原组 ACK/closure 仍冻结。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
