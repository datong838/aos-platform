# SC4-5l6j E 代 P02 current 控制链验证

日期：2026-09-15  
代码基线：`625f9233`  
范围：六步中的第 6/6 步；E exact preflight、SourceSelection、RuntimeControl 与 ScheduleBinding。

## 结论

P02 current 入口已从历史 D 完整切换到 E。预检只接受 E create Receipt、E active@5、generation `ebaa620a-8831-4c2a-b971-788383f352f8` 的 ready/enabled/unfenced binding，以及 Niushop 1.23 签名内容。旧 D installation 不匹配时失败关闭。

新的 SourceSelection、RuntimeControl 和 ScheduleBinding 已按顺序写入，Schedule 保持 disabled。绑定读回的 installation/generation/controlRef 与本波新引用精确一致，历史失败 Run `scr-f22003e66e544ebe` 保留且 executor_stopped=true，canary claim count=0。

## E exact preflight

- outcome：`PRODUCT_CURRENT_PREFLIGHT_GREEN`
- current installation：`1c08edfb-ec0d-4abb-a411-7b6ec0d6066a@5`
- lock：`sha256:f52df338f30b9f7d21fe31ec3ff1fc1a1c108c7c9e4cab3e3ea583ca31ccaa51`
- generation：`ebaa620a-8831-4c2a-b971-788383f352f8`，binding revision 4、epoch 3、ready/enabled/unfenced
- package：`platform.ecommerce.niushop@1.23.0`，content hash `sha256:55b29795b73d5be0f28bd68fafc48c8dd7aa42c65eb5ea130a307326e7534117`
- P02 mapping：revision 1.23.0，content hash `sha256:4ef146db758ca22e756857dc6cb6e8f615374dc2dccb96bc8835c93f8123d7f0`
- read spec：`ns_goods`、28 columns、Product、rowLimit 1000、timeout 30 秒、maxSourceCalls 1
- 预检计数：sourceRowsRead=0、approvalsWritten=0、businessWrites=0

## 新控制引用

- SourceSelection：`source-selection-4bfa23da-510f-482e-92ca-1ec126b3dc5c@1`，hash `sha256:6928b8ace54d821ff59449922aa2d4a984b98c6200845336c249806c9c9a74c8`
- RuntimeControl：`pipeline-control-3a9f4169-57f4-4fa4-badf-9f2c0d0e035f@1`，hash `sha256:81808f3055a69e0c3d601a1adae8480af0a858e7ebb5c09334103218a8401cb8`
- ScheduleBinding：`schedule-control-eeff7221-b61f-4ca5-a6cd-f333947a1cff@3`，hash `sha256:ad8c1b27cc3714f34387648f0a79d60b0b510736c9866edadfafeb0b9f1c6b7a`
- Schedule：`sch-p02-qyh-controlled-20260913-v1`，最终 enabled=false。

## 不可变证据

| 文件 | SHA-256 |
| --- | --- |
| `p02-e-current-preflight.json` | `57f3091d4ec2eaf554a42373e4f9fafa979904acb5f8b633331add6541ac05b6` |
| `prepare-result.json` | `b9f41234129df0dad52b0bbb3b58494084b7064cdf3cbe96f6cf98d7c52e91da` |
| `selection-result.json` | `a35697a8ba9d95536d93a0d036c55da66fedc8536e799e2435c6b222c90c8f23` |
| `control-result.json` | `0e9e312a450aaceaa722042c401f05f5995c1ec970df2f2033a469f1e8b3cb06` |
| `binding-result.json` | `3bae27cf9fc8c0e42083e11510deb2c15f61b6c0ede519c29c19a2887034ac5e` |
| `observe-before-execute.json` | `8e38f72080ffe3d51662bdea8eb92dbf0379e4d85c8f6748aa4817fe625e57eb` |

## 自动化验证与边界

E preflight、业务控制器和重装控制器定向测试共 `24 passed`，包含旧 installation 拒绝、binding 字段漂移拒绝、执行前 schedule/ref 比对和失败 Run 不冒充成功。`git diff --check` 通过。

本波 SC4-5l6j 六步完成，关闭了 P02 源数据会在源修改时间不变时发生库存/销量漂移而撞旧 Receipt 的包合同缺口，并把修复安装为 current。尚未声称真实 P02、Dataset 或 ProductEvent/Case 成功。

## 下一波 SC4-5l6k

1. 冻结 E 新控制引用、历史失败 Run 与执行前 stage count，确认 API、Host、三个 OCI、Schedule disabled。
2. 形成一次性真实 P02 执行与观察方案；新 Run 只允许一个源调用，失败后不换 key 重发。
3. 触发一次新鲜真实批次并立即恢复 Schedule disabled。
4. 验证 Run succeeded、65 行 observation 版本 Dataset exact 完成、Receipt/checkpoint 幂等且 canary 零写。
5. 观察 ProductEvent Worker 自然创建 Occurrence/Case/Run，并验证 sourceRefs 指向该 Dataset；若不触发，只诊断正式缺口。
6. 落证据和提交；若第 5 步成功，下一波进入数字同事分析、来源建议与 exact 评审；若失败，下一波先补自然触发合同。
