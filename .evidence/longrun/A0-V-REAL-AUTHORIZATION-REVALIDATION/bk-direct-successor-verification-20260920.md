# BK 直系后继激活验证

## 结论

`BK_DIRECT_SUCCESSOR_GREEN`。BK installation `8c78f903-ebd8-4589-97a0-afad76e209e0` / generation
`9ea4ba9d-1ef8-45a6-9060-1e4f37c87038` 已从 BJ exact detach authority 创建并激活。

## 父权威与创建

- 父 disable operation `2300de61-0b54-413a-97e7-4e37e3b20768`、detach Receipt
  `2c5d28d5-cfcc-474d-827d-d0031d0de4d8` / hash
  `sha256:9fff94f0bc18f763292002f838bb0f197e9548e59eefe92d2722cd71d307281d`。
- preflight 固定 BJ Binding rev8/epoch4 disabled/fenced、三资源 released、legacy rev158/group185、definition
  rev112 disabled及业务零副作用边界；BK 使用全新 identity、lock
  `sha256:462bc93fcd577556199e60c70eb21b3e5ae539b310f101aeb6095b9613babf71`。
- configuration `47ba0191-fb87-4df0-a8f2-58ca17579c05` / hash
  `sha256:ffe36da2bc248d648e78a8585fd22c3ea8d991dff5b0e03200f49fa13a6391ee`。

## Runtime 与切换

- 唯一 Runtime Host PID 10991 完成 runtime-apply `ec59c319-ddeb-4022-97da-b232c0cf11fa`、verify
  `6ba78215-f331-42cb-980d-c60d1a9a8c24`、configure `780bd52e-a6b0-4059-a587-32f572bc7547`、enable
  `c0b41d71-3bb5-47dd-a744-4f39324a4d4c`，均正式 succeeded。
- registration Receipt `78309e60-90f9-4716-82ce-1af2059f05f5` / hash
  `sha256:d140cb8fac4ddb825a1f0562880c3d0e91ca15f986d8a5b15fefd74d23c9c0b7`。
- cutover operation `30355379-f48e-4261-91cc-533f13c34ab6` 串行完成；prepare/commit/validate/resume Receipt
  分别为 `1c375026-d24b-4d50-a6f0-a545c41b94d9`、`54822f33-82c4-47ba-82bf-19554f61e722`、
  `2534ea1b-eec0-4c70-946a-fa26c5b73a31`、`ababe7cb-b9fc-4c02-a807-c02509697bf6`。
- 最终九路 extension rev159/group186；Binding rev6/epoch3 enabled/ready/unfenced，三资源 live；definition
  rev112 disabled。

## 健康与边界

- 健康续租从6增至18，delta=12，last sequence=31；attempt=0、running=0、unresolved=0、runtime pending=0、
  canary=0。
- 十二 saved Run running、十二 Dataset Receipt；Store Receipt、`ecom_link`、projection pending 均为0。
- 私有结果哈希：preflight `a1aa183ae0bf14a9360f940efd5efaa5dad77a97842039eb0ff925e4bedc85a2`，
  create `0d3298bb02f754eecff4d42cb5c8d8cab97098ec2e28a4a77cc5e18678379213`，registration
  `86f52913765eef4b82d4fdb19b0db8e783673069a79d40f19b7ef834b3faffe6`，health
  `5fef808504c3f4c1c384fbbe7c4132fa0d16406f12a524b43c1fb174439da1d5`。
- 本波不读商城源数据、不启动 snapshot worker、不手工 `run_definition`、不 push；230 L0 继续挂起。

## 下一波

方案先行进入 BK saved-snapshot recovery：definition rev112 disabled、attempt=0 下纯 HTTP 先行，随后转移并只允许
唯一自然 worker/attempt，观察间隔固定50秒。
