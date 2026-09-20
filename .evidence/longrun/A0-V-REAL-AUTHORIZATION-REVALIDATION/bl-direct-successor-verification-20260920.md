# BL 直系后继激活验证

## 结论

`BL_DIRECT_SUCCESSOR_GREEN`。BL installation `ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc` / generation
`116d12fc-93bc-4071-a973-fdc6830ea8b1` 已从 BK exact detach authority创建并激活。

## 父权威与创建

- 父 disable operation `6db4b69b-0dbf-4a77-ac71-23cef91c6f50`、detach Receipt
  `dfce56ec-4bff-4793-a5d5-dab4ad45aa1c` / hash
  `sha256:3fc2b8a9c3614912b1ac7a9c0d127677f3cc0187ed5c24209da10a963c71dca4`。
- preflight固定 BK Binding rev8/epoch4 disabled/fenced、三资源 released、legacy rev161/group188、definition
  rev115 disabled及业务零副作用边界；BL使用全新 identity、lock
  `sha256:47af46b5658b7952f9d3068466ba06c6203e51fef899c5d661026230893b334e`。
- configuration `1d25aa72-86b9-4d5a-8523-0e4a4a013a71` / hash
  `sha256:4f85fd85b307b20ed1065a774e0af26e7692754bf14d47f8d5430d74c083cf9a`。

## Runtime 与切换

- 唯一 Runtime Host PID41833完成 runtime-apply `319f1b2b-1cdf-49de-bc0c-b9779f018200`、verify
  `e19700c5-e9bb-49fe-955f-d8e5d5e68563`、configure `1df76901-805d-423a-8586-a45e4a2bea18`、enable
  `2b643a61-eee9-495a-8a78-8a379a6b8a65`，均正式 succeeded。
- registration Receipt `e455fce1-310f-4dcb-8ace-51a5e5bafe5e` / hash
  `sha256:6c6beb3580b5fc27eaff3884e315f2e40bad8ab71ae3c5aed8b3f22f59ebbc4e`。
- cutover operation `7acaa1be-bfe3-481b-9841-c4b09779b4f8` 串行完成；prepare/commit/validate/resume Receipt
  分别为 `e9d5c114-645e-4c74-8525-b27035ede16b`、`76aed908-ef7b-4e84-b9c4-f30014cc143d`、
  `fdf6e5cd-2923-4352-8299-f37cdfe37955`、`fa198cdf-1245-4606-b448-4d74276026e2`。
- 最终九路 extension rev162/group189；Binding rev6/epoch3 enabled/ready/unfenced，三资源 live；definition
  rev115 disabled。

## 健康与边界

- 健康续租从4增至16，delta=12，last sequence=29；attempt=0、running=0、unresolved=0、runtime pending=0、
  canary=0。
- 十二 saved Run running、十二 Dataset Receipt；Store Receipt、`ecom_link`、projection pending均为0。
- 私有结果哈希：preflight `2dd0a5d71eabcc66a120e0e2e06aa2019935a570c00269dee4a40a1dbd7b8419`，
  create `dfa936417e9469089054812cb089a80812115d617d521600f68af617092397eb`，registration
  `100f04e45e92e38fa70aa72bcf97ee0731a47543454c3443cc1ee46473bec0e0`，health
  `3b0c9f42a02bd10033860f8bec5db81f9f1dea9344f48e955595fa59c4f8528f`。
- 当前唯一 Runtime Host PID41833，第二 Host=0，snapshot worker=0。本波不读商城源数据、不手工
  `run_definition`、不 push；230 L0继续挂起。

## 下一波

方案先行进入 BL saved-snapshot recovery：definition rev115 disabled、attempt=0下纯 HTTP先行，随后转移并只允许
唯一自然 worker/attempt，观察间隔固定50秒。
