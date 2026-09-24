# W5b1 DS 当前配置 rev2 与 Runtime Binding 恢复计划（2026-09-24）

## 依据与边界

W5b0 `36460253` 后 DS 安装 active/etag5，binding rev9/epoch5、desired disabled、enabled false/fence true，旧定义 rev3 disabled、12 个 schedule off、活跃 attempt 0。DS Config `5423ebf3-4928-4950-b55c-ea2662f84bc8` rev1 的 Policy ref 为旧 rev12；W5a2 当前 Policy 是 rev13。复习 `ecommerce-runtime-host-and-growth-1.5-replacement-plan.md`、`w5b0` 验收、`a0v_ecommerce_1_7_configure.py` 与 `configuration_store.append_configuration` 的 CAS/同族后继规则。只修 DS 当前配置/运行绑定，不读取商城源、不创建 source selection/业务 Run、不打开旧定义。

## 文件与串行步骤

- 新增 `scripts/a0v_w5b1_ds_config_refresh.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5b1_ds_config_refresh.py`，私有批次 `.../20260924-w5b1-ds-config/`；复用现成 W4 配置 Owner 执行链但固定 DS ID/generation/configRef、独立幂等键和新 state，不能修改旧 W4 文件。
1. 只读核对 m1、8080、DS etag5/binding rev9/epoch5 disabled/fenced、旧 config rev1 exact、Policy rev13 当前且 Budget 有效、12 schedules disabled/attempt0/canary0；冻结新 state 路径。任何漂移停止。
2. 用正式 `append_configuration(previous_ref=rev1)` 一次写同 `configurationId` rev2，文档只替换为四来源当前精确 ref，尤其 Policy rev13；O_EXCL/0600 留 stage 结果并独立回读 hash/前驱/receipt。未知提交边界不重新 stage。
3. 用正式 `RuntimeConfigurationService.request(kind=configure)` 一次，使用新 configRef、当前安装 etag/binding CAS；只读观察唯一 operation 至 terminal。配置后必须 desired disabled/fenced，12 schedules 仍 off、attempt0。未知状态不补发。
4. 前述 GREEN 后，用正式 `request(kind=enable)` 一次；观察唯一 operation 至 terminal、binding enabled/ready/fence off，并复核新 configRef/epoch、资源状态、canary0。旧定义仍 disabled、12 schedules off，因此不得主动发起业务任务；如果当前四来源授权变更则先停。
5. 写 verification、测试、提交 m1，不 push。下一波 W5b2 另用当前 Config rev2/epoch 生成 12 条新 selection→control→schedule binding，旧 selection/controls/options 不复用；再进入定义更替和自然调度观察。

## 停止条件

任何 command 失败、返回未知、operation 非终态、Host 双实例、receipt/配置 hash 不一致、旧定义意外开启或 schedule enabled，立即冻结本波并只读对账。不得重发任何 stage/configure/enable；不手工 `run_definition`，不读取商城源数据。
