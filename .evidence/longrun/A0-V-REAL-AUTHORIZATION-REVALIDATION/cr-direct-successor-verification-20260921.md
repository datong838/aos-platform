# CQ 正式退休与 CR direct successor 验证（2026-09-21）

## 结论

`CR_DIRECT_SUCCESSOR_GREEN`。CQ 以零 attempt 的 blocked-refresh 边界完成 disable
settlement，九路从 rev252/group279 经 fence 收敛到 legacy rev254/group281；CR 仅凭
exact detach Receipt 创建、启用并 cutover 到 rev255/group282。CR configuration 直接引用
current RuntimePolicy rev11。全程未读取商城源数据、未调用 `run_definition`、未重发未知
结果。

## 1/6 plan 与冻结基线

HEAD `56ea986e`；CQ installation `fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80` / generation
`ae8a1005-99fb-48c5-9dfe-8f76590bc0c8` 已 detached，Binding rev11/epoch6，definition
rev193 disabled，attempt=0。基线为十二 Run/Receipt 与零副作用。

## 2/6 CQ 正式退休

已在 `56ea986e` 封板：disable `36c3d6ca-db24-4553-a0ec-8748006b3dd8`，fence
`839b0c44-68a0-467f-b8ae-0fe1d8e8a3bf` /
`sha256:03b41b959cd7f80f12f204cdab85c7cbefa41965a25263b3d1ecef7043511f63`，detach
`2d8a382b-90f1-46c3-9100-c2310a949914` /
`sha256:3b618e589557064bf049dd344fa9bdc345236d22a38ec2c1558d2a968d08b432`；Host 8784
SIGTERM，三资源 released。

## 3/6 CR lifecycle

CR installation `913cb7a1-4912-471a-abbf-452e3ce999a9` / generation
`a4a16448-5581-4948-b962-777ff601e855` / lock
`sha256:c3513e45b002c90a810034eab554ed58c6aba4123be24349bbba0f7d24777334`；configuration
`6b8252ba-99c7-46bb-9618-69f107834707` /
`sha256:81dfc50ef7a2885770c70adc46669e84af6a0d9a645b2e816ef61c2418f5a3cb`，policyRef 为
RuntimePolicy rev11。prepare `38aadd42-6693-467f-abde-cc36924fef2f`，唯一外置 Host PID
12390 自然领取；verify `96e51497-5a65-47aa-962b-0ac9bf9e5214`、configure
`4fbbb15c-46e7-414a-8b37-71dafd4cead9`、enable `61d0f970-415e-4fbe-aabf-d704bf443ba9`
均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `f3111a42-813d-417d-81fe-87e1161537b9` /
`sha256:82e564f57f993cf44a3d40ad68169e7a049e4cdce219414fc70707fc31f4be66`，cutover
operation `59e26a0e-c144-479b-ba78-b8cba414b006`。approve、prepare、pause、commit、
validate、resume 全部完成，commit Receipt `3d6b7aab-adc7-4ef5-beff-8df44da46ee0` /
`sha256:c54a47618700d1c429b0afab9cf3d2b95c3ccdbef5b1b64ca6ed67908f3775c9`，resume
Receipt `819f7956-9462-4128-9cda-f4b09ed5b361` /
`sha256:319f0570869bd66b2956f8001ec3105b0de2a1e11d6a0aee58cb96a218d90a9e`；九路全部为
CR extension rev255/group282。

## 5/6 健康观察

只读 repeatable-read；baseline renewals=3，36 个样本后 renewals=15 / last_sequence=28，
`CR_HEALTH_OBSERVATION_GREEN`。attempt=0，三资源 pending，canary=0。

## 6/6 副作用与测试

12 members、12 running Run、12 Dataset Receipt 未变；Store/`ecom_link`/projection=0。
专项测试通过。下一波：CR saved-snapshot recovery。不 push，230 L0 继续挂起。
