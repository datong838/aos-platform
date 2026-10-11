# 重启恢复维护复审（2026-10-11）

规则：231、原 current159-maintenance-20261010 合同、租户双边界；原 m1 唯一写者。复审基线 3a3e3ace0 / AOS-001790。

## 实际通过及范围
- 原权威卷恢复与当前签名 API 启动证据已落盘。原旧 API 自启动冲突的纠正有独立意图/终态；不重放迁移。
- 浏览器检查后的全库只读比较覆盖626表；完整结构化快照与原基线精确相等，差异类别为空。不是仅比较行数。
- 八电商工作台实际 DOM 与截图均呈现入口不可用，属于当前未开放状态的禁入验收。重新读取目录仅发两项 GET；不证明正向工作台功能。
- org-org/dev-project 目录响应200且为空；dev-org/dev-project隔离canary403。使用既有开发预览身份，正式业务身份未验收。
- 启动制品与注册入口专项35 passed。测试结果不能替代运行期授权。

## 用户澄清后的实例归属只读核对
电商域承载八工作台通用能力，栖月汇组织下承载具体安装与实验。对当前权威库在 BEGIN READ ONLY / ROLLBACK 内精确查询：meta_org 与 twa_org 中 org-org 的名称均为 org-org；meta_workspace 的目标名称为 dev-project。目标安装 ccdcb0f0-1040-4bc6-aa0c-d045f5689813 名为“栖月汇当前源码电商八工作台隔离首装”，当前修订3，active_revision为空。此证据支持既定目标scope内存在栖月汇命名安装，不证明组织展示名称已校准、实例已激活或业务授权成立。未调用带ensure写入的组织GET接口，未改组织名称或安装状态。

## 未完成与下一步
本轮未证明 PG→API→Web 按顺序全部重新启动：Web沿用机器重启后的进程。完整维护Task不据此签发Delivery，不能将机器重启检查等同于全部维护合同完成。先核原Web启动合同及现有终态，再按既有授权补齐必要门。
原生完整ending为另一已登记候选，要求全8节点/四证书/Source/风险/Receipt/固定点/最终时钟/实际COMMIT及提交后unknown保守处理；现有纯reader及隔离通过不替代该合同。正式Root/Host/worker/Provider均不得由本报告放开。长期Goal继续active。

## 证据摘要
- `signed-api-verification.json` SHA256 `768a8fe080a539bfef96e2053fad099a5b317721feb2813f3ae7efd453f37797`
- `post-browser-snapshot-comparison.json` SHA256 `9a1158e8abc143b00927299179053b55de2dde4e75256410ac64a6fc05421d6e`
- `browser-dom.json` SHA256 `83a2f006f3a95a7631acb9a6498731ca0e9235921efb758ef36ed3e66036671a`
- `browser-refresh.json` SHA256 `e6738052c56a6b291bffa2c07b2d61e30d3c9da1ab26bf1c45f4708515f11f56`
- `tenant-readonly-probe.json` SHA256 `6913a5c9a43d6c5adc5b640d53004f632aa75e41305cef7ca24a9032e12b04ce`
- `startup-regression.log` SHA256 `c4d05229fd309c9b765f61b04828132774c8037ccd7a7a8a4243db511070dccb`
