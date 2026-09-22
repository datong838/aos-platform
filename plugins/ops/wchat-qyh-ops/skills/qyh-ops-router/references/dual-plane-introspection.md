# 双域全息内省

## 目标

通过“浏览器全域观察 + 数据库全域内省”建立对一个店铺及其平台的可审计认知，使后续 Agent 不再依赖临场猜测或反复摸索。

## 两个观察域

### 浏览器域

由后台/小程序观察技能负责：
- 管理后台全部一级、二级菜单与关键页面；
- 商品、订单、会员、营销、财务、数据、店铺、设置等运营流程；
- 消费者首页、商品、内容、购物车、下单、会员、分享、体验码和店主旅程；
- 页面对象、筛选、状态、按钮、反馈、阻断和真实交互；
- 经明确授权执行的动作及动作后权威回读。

产物是 PageMap、JourneyMap、ActionMap 和 UI Evidence，不是数据库事实。

### 数据库域

由 `qyh-data-onboarding` 以 Data OS/FDE 身份负责：

- 通过受治理 Source `niushop-qyh` 和 MySQL SSH 隧道盘点远程 Niushop Schema；
- 识别表、字段、主键候选、逻辑外键、状态、时间、PII、基数和分布；
- 对照 P01–P12 mapping，发现已治理范围与长尾缺口；
- 形成 DataProfile、MappingCandidate、Dataset、lineage 和 Ontology Candidate；
- 通过 DataFulfillmentReceipt 把受控结果逐层交回。

产物是数据产品与本体候选，不向 Workshop 暴露 Source、SQL、连接参数或原始客户明细。

## 四类对账

1. **页面功能 ↔ 表与字段**：页面上的订单、商品、会员、体验码、佣金分别由什么数据支撑。
2. **页面状态 ↔ 数据状态机**：销售中/仓库中、待支付/已完成、客户/店主等状态是否一致。
3. **用户动作 ↔ 数据变化/效果**：上架、分享、下单、绑定、结算会改变哪些对象，产生什么 Receipt 和经营结果。
4. **已覆盖 ↔ 未知区域**：哪些页面没有数据映射，哪些表没有页面解释，哪些语义仍是 Candidate/Conflict/Unknown。

## 首次全量模式

首次接入新平台或新店铺时：

1. 冻结 scope、purpose、允许观察范围和隐私边界；
2. 浏览器域完整建立前后台地图；
3. Workshop 提交 DataNeed，由 Data FDE 完整建立 Schema inventory；
4. 两域通过对象、身份、状态和时间语义对齐；
5. 输出 PlatformIntrospectionSnapshot：PageMap、SchemaMap、DatasetMap、OntologyCoverage、冲突和未知；
6. 形成平台研究方法 revision，供下一个同平台店铺复用。

“全量”指覆盖面完整，不表示复制全部页面、导出全库或采集全部 PII。采样和持久化仍遵循最小必要原则。

## 后续增量模式

已有稳定 Snapshot 后：

- 页面任务按 PageMap 直接定位；
- 经营分析按 Dataset/Object/Metric 直接查询；
- 缺口通过 DataNeed 精确补证；
- 只对页面变化、Schema drift、数据质量异常、指标冲突和新经营问题扩展探索；
- 每次变化生成新 revision，不覆盖旧证据。

## 分层边界

```text
浏览器观察专家 ─┐
                ├→ Data OS → Data Semantics → Ontology → AIP → Workshop
Data FDE 源库内省 ─┘
```

- 浏览器观察数据先进入 Evidence/Landing，再经质量与语义门；
- Data FDE 持有源接入能力，Workshop 只持有 DataNeed、Handoff 和 Receipt；
- Ontology 确认对象/关系前，MappingCandidate 不得成为经营事实；
- AIP 形成问题、机会和方案，不能越过数据质量和 Action 治理；
- Workshop 展示、决策和受控执行，不创建数据第二真源。
