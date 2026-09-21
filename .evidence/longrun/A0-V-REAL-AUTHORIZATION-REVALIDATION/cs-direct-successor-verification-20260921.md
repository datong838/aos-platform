# CR 正式退休与 CS direct successor 验证（2026-09-21）

## 结论

`CS_DIRECT_SUCCESSOR_GREEN`。CR 以唯一 failed attempt rev5 完成 disable settlement，九路从
rev255/group282 经 fence 收敛到 legacy rev257/group284；CS 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev258/group285。CS configuration 直接引用 current RuntimePolicy rev11。
全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `eb1d93e5`；CR installation `913cb7a1-4912-471a-abbf-452e3ce999a9` / generation
`a4a16448-5581-4948-b962-777ff601e855`，binding rev6/epoch3，definition rev196 disabled，
唯一 attempt `11e98b8f-d898-4b1b-a6fc-c210bb44e5d7` failed rev5。基线为十二 Run/Receipt
与零副作用。

## 2/6 CR 正式退休

Host 12390 SIGTERM 后 binding rev7/epoch4、三资源 released。disable
`0667be2f-3ebd-484b-99f0-dfb135a6f9c2`，fence `1c639774-6897-4edc-a993-41374a97c949` /
`sha256:0b0ba31d3adf278acea9cf1d70a31e9d4f13dac6206390563ed0112914f21356`，detach
`14c1b753-d557-4441-bf7f-89ad5ab48be5` /
`sha256:bd7ff2a43c944fe8aed88f89e9af82b511a36a8e029d86bb2428369ba3f9cc06`；binding
rev9/epoch5，九路 legacy rev257/group284。

## 3/6 CS lifecycle

CS installation `ff72acba-1e59-4da3-b92a-18737e18e9d2` / generation
`01a1719d-1109-440f-a233-1c5a6adb0d81` / lock
`sha256:1b37fab980943517deeec01b88f1ebe119b6143fc7db13c42ca9e4756e3af65a`；configuration
`de040f32-54ee-4a51-82b0-09b0142c0f64` /
`sha256:78559f2d3230bc55f974141662631d2157c7ac9aabc34efb41f1c334f1d79238`，policyRef 为
RuntimePolicy rev11。prepare `7b8e60bf-8cb6-4e6a-9a50-05f6e3b4fc3c`，唯一外置 Host PID
16307 自然领取；verify `c376984b-ddef-4a05-9228-5c9539e72fdc`、configure
`c640f50d-84df-4524-8bfd-a1d644036377`、enable `64c4521a-309d-4470-ad65-f3cbb766e351`
均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `c9cae847-a2c6-4e5e-9407-ebb6b9abdf96` /
`sha256:15709955fada71b289971c5cabb0013bbd461a55082cd766a48bf79f06be7ea7`，cutover
operation `d4036350-f591-4064-abf2-4e2849115c57`。approve、prepare、pause、commit、
validate、resume 全部完成，commit Receipt `6d1a70ea-e806-4268-91d5-a40e677abedf` /
`sha256:ad224e73a41fde6a1752106a55b6ef1a5be2cf4c7617d028ca2b0248de4858c5`，resume
Receipt `4a4b680b-abd8-49cc-89c4-97cd3c469d57` /
`sha256:0f3b4cda5d068c193beb23ea9c109fa79fd84b7d7deb45723d91318bfe1bdd7b`；九路全部为
CS extension rev258/group285。

## 5/6 健康观察

只读 repeatable-read；baseline renewals=3，36 个样本后 renewals=15 / last_sequence=28，
`CS_HEALTH_OBSERVATION_GREEN`。attempt=0，三资源 pending，canary=0。

## 6/6 副作用与测试

12 members、12 running Run、12 Dataset Receipt 未变；Store/`ecom_link`/projection=0。
专项测试通过。下一波：CS saved-snapshot recovery。不 push，230 L0 继续挂起。不使用定时 wake。
