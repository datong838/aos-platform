# 内部草稿读取失败与历史暂存区分方案

Rules/231/AGENTS同owner/base2030/16:00UTC精确CreatorGrowthPage.tsx与原test，其他CSS/组件/AIPStore不改。上位产品为六类内部准备/版本精确/人审且外部触达独立；继续全部长Goal。本波修复读取失败语义，不借此授予任何内部或外部命令权限。实际原API仍f005、Web6c，新有界reader已代码候选5a1855482但未接线。

现load吞list错误且未改变旧workflowDrafts。修复引入 workflowReadState（loading/ready/failed）与独立固定业务错误文本：load开始设loading，新id胜出的完整list成功为ready，null为failed。空[]也是合法ready，不能与failed混同；错误不输出异常/SQL/secret。保留旧workflowDrafts仅为明确标记的“上次读取的暂存内容”，verified current accessor在state!=ready时不存在；history useEffect仅访问verified current，无当前准入不继续history读取/恢复。响应stale id仍现有request ref拒绝，不引入复制客户端租户状态机。

不销毁用户正在编辑的字段或已发生操作Receipt/idempotencyKey。PreparationPanel增加readUnavailable prop，读取中或失败时提示“当前内部草稿暂未读取，暂存内容不能作为当前版本操作”；如果有cache，状态文字必须明确“上次读取”。保持cache prop ref/revision不因失败变动，避免现hydrate effect覆盖未保存输入；失败时不自动清空编辑，不改原成功更新version的水合语义。触发明确重新读取后不同服务端新revision仍原hydrate处理，不宣称解决全部多用户编辑冲突；CAS版本仍后端权威。

所有真正workflow命令按钮(save/submit/approve/reject/restore)及新建一份仅state ready才采用原busy/字段/status判断；executeWorkflow入口还须guard readstate!=ready，早于生成intent/key/任何client call，防仅禁button不足。关闭/导航/只读重新读取可用；准备表单可以查看/保留暂存，但不能把cache ref发给服务器。不自动重试execute，不重置unknown/attempted命令key，不复用read成功作预算/审批决定。原命令成功+history失败保留新draft/Receipt，与list读取故障是不同state和错误来源；原正常读取/空态/内部合法流程保持。

RED：首次list失败→明确unknown且所有命令0调用，真实empty→合法入口；已有draft/编辑后重新读取失败→cache明确历史/不再verified current/所有写按钮及restore禁用/输入保留/Receipt不消失；重新读取成功→当前状态恢复只读显示和既有guard，失败期间没有execute重发；成功命令history失败原回归、stale async load不覆盖新snapshot。先独立plan合法消费、最小2文件修改，Vitest本组件/API strictclient及相邻工作台、typecheck按已装环境（不改pnpm锁或重装）。真实浏览器所有动作限read/UI，不保存/approve/execute；故障UI验收使用授权隔离localfixture/受控client响应，不在原库造坏数据。按原稿三视口只核状态显示/不遮挡和主结构；1280按钮裁切与价格255px仍另待，不能P1合格。

UI与root接线需各自代码质量/精确最新已提交冻结/API和Web fresh维护门/原真人GET菜单/650指纹/独立现场Prime及准确各scopeDelivery之后才同步Authority/Prime。日报及每次aos仍最新m1原权威卷完整PG→API→Web；aos-2不重启。完整BudgetC/用户最后真实批准/原部署/自然首链/安装全生命周期/八场景/全视觉/观察发布仍未完成。

## 自查补充：同一事件批次的即时禁入

state更新需要React重绘；同一批次先reload再旧按钮handler可能仍持旧ready闭包。增加仅本地读取状态的即时ref：load开始立即false，ready已渲染后effect同步true（当前响应仍经request id裁决）；命令入口同时检查state与ref，未重绘不能借旧闭包触发client。不是业务权限或审批第二真源，不修改请求键。新增单批次reload+旧save点击0execute的RED反例，再复跑相关验证；这是原方案“命令入口guard早于任何调用”的必要补强，范围与Goal不变。
