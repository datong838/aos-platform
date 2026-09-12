# 工作台目录可见性验证

2026-09-12，基线 cf078885。真实 org-org/dev-project modules 接口05:54:35Z返回 count=0。旧目录按 legacy_content_predicate 排除 runtime lock，正式调度登记未接通。不解除该隔离；安装 active/运行 enabled 不代表入口可用。

新增测试先红4 failed/5 passed；最小实现后导航、宿主、目录上下文15 passed，TypeScript、diff check通过。覆盖空目录重读后出现真实目录项、读取失败不推断安装、租户切换及已有模块回归。既有宿主测试有未mock代理目录请求的URL解析失败日志，由原失败态处理，不作为真实服务成功证据。

真实IAB tab8 /workshop/operations：侧栏“暂无可见工作台入口”和重读按钮；主区“当前工作台入口不可用”和重读按钮。不再误报模块未安装。浏览器确认读取后状态，成功恢复通过隔离客户端测试，未伪造主库目录。

05:57:55Z持续运行863.89秒、14续租、3容器running，binding ready/enabled/unfenced revision4，canary installation=0，详见 workshop-visibility-continuity.json。未改源库、权限、调度或执行经营动作。

下一波：核对经营参谋计划为空的入口及真实任务图谱，定位自然触发、评审续跑与Wiki候选的实现缺口，继续不依赖被拒SSH身份和待批登记权限的工作。
