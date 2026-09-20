# BJ 直系后继激活验证

## 结论

`BJ_DIRECT_SUCCESSOR_GREEN`。BJ installation `2c3972b1-67c1-400d-aa63-b90de369f5de` / generation
`8dafd4ae-d42b-4f2f-accb-b5a49e7c9a3b` 已从 BI exact detach authority 创建并激活。

## 父权威与创建

- 父 disable operation `96f687af-97ea-44cc-97e6-0c1cd292a8cf`、detach Receipt
  `64375b18-389a-4e5b-bd17-c7e03a63edd6` / hash
  `sha256:0962da63b333d3bf94ea9cd9272e2aeba8afad44e3c678c560b4bd4872b56ddd`。
- preflight 固定 BI Binding rev8/epoch4 disabled/fenced、三资源 released、legacy rev155/group182、definition
  rev109 disabled及业务零副作用边界；BJ 使用全新 identity、lock
  `sha256:d01e0d465ac65672a7edac4be6b453d16958037d15fff75220b6d5dee4458128`。
- configuration `552451f8-f585-42b5-a992-7a366aaca1be` / hash
  `sha256:bf55da36296ed24bb71e29d3a95639580239ef449ed36ab4edecac9e4f1d0a5d`。

## Runtime 与切换

- 唯一 Runtime Host PID 10991 完成 runtime-apply `62ebeee2-aaef-4c49-acab-8d56ddb44ac0`、verify
  `c7e1a68c-4e9b-4aa0-9060-11f30af4b52c`、configure `f63078ff-8da5-4f58-b66a-a352c5f274ad`、enable
  `3c3baef2-7416-431f-aade-640a67edc549`，均正式 succeeded。
- registration Receipt `39dba3e9-33c6-47f3-ab78-5dc234cfdd90` / hash
  `sha256:d23d74374a50e66b6f9c69a8a523bcad2e8dbafd97a09811ea981829e6f83b11`。
- cutover operation `337aa516-42f1-47fc-afb7-980d3c0e62e1` 串行完成；prepare/commit/validate/resume Receipt
  分别为 `a771c94c-b04d-4d55-bebd-341e7956d660`、`725bf692-3669-4482-af60-ceecdc09cffa`、
  `fa5fbc75-6b43-4381-8871-689f99790d4c`、`3e1fa4a7-2fbd-483c-affd-f4c27712ebbd`。
- 最终九路 extension rev156/group183；Binding rev6/epoch3 enabled/ready/unfenced，三资源 live；definition
  rev109 disabled。

## 健康与边界

- 健康续租从 4 增至16，delta=12，last sequence=29；attempt=0、running=0、unresolved=0、runtime pending=0、
  canary=0。
- 十二 saved Run running、十二 Dataset Receipt；Store Receipt、`ecom_link`、projection pending 均为0。
- 私有结果哈希：preflight `a9dfeb4476563249984668ecec60d503f82432da907eda795e71895d6938b888`，
  create `bdd935661c5abf6f90dc4f12910a6114eb1892344b6c92ad29240929a0b80269`，registration
  `9189c448bc6c9f7005acdc955d3f56e2c7de44a577f4244e927b7537b786236b`，health
  `a073c5a2c067698d6d818ed9949e9000a90afff616af7ac02902e1d27306f341`。
- 本波不读商城源数据、不启动 snapshot worker、不手工 `run_definition`、不 push；230 L0 继续挂起。

## 下一波

方案先行进入 BJ saved-snapshot recovery：definition rev109 disabled、attempt=0 下纯 HTTP 先行，随后转移并只允许
唯一自然 worker/attempt。
