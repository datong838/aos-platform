# P02 栖月汇商品真实首读验收

2026-09-13；代码基线 ee6c0aea，登记证据基线 5b6ddb69。m1 串行，无 push，无生产发布或 230 L0 操作。

## 已验证

- 正式计划 sch-p02-qyh-controlled-20260913-v1 经既有 SourceSelection、RuntimeControl 和 schedule binding 接入，run scr-bc63f0d8437d4eed 读取真实 ns_goods/site_id=1，共 65 条，耗时 12555ms，executor_stopped=true。
- 数据回执、原始命令、派生命令与 Owner 投影完成证据交叉核对：expected=65、projected=65、pending=0；dataset build success，rows_written=65。详见 p02-first-authoritative-v1.json。
- 仅消耗一次 SourceClaim；负租户可见 Receipt=0。计划已通过正式入口关闭，后续独立数据库读取再次确认 disabled。未再次访问商城源库。
- 05:02 对保存的原始命令检查：39 条 ACTIVE、8 条 DELETED、18 条 INACTIVE；8 条显式 tombstone。

## 未通过或不覆盖

18 条 INACTIVE 的 canonical_value 仍为 unknown，虽然 raw_status 保留，但尚不能宣称所有消费者具备正确的下架语义。下一波先核对产品状态契约并修复这一缺口，再进入经营候选分析，避免下架商品进入可经营集合。

本证据证明数据读入与投影，不证明自然 Case/Run、经营分析、人工评审续跑、八工作台或连续经营观察完成。SKU、关系链、生产身份收敛和真实前端领域包仍有未完成项。NULL 商品内容兼容性未由本批数据证明。

附加只读统计曾因把结构化状态作为 Counter 键而失败，修正为规范 JSON 后成功；失败过程没有源调用或业务写入。本波无生产代码修改，不扩展或重复已通过的测试。

## 下一波

先审查下架状态语义和消费准入，形成最小变更方案、补有意义的回归测试并验证；随后完成正式业务路由登记及源事件消费者，使真实数据通过产品入口自然生成 initial_store_analysis，不以手工接线代替验收。
