# Y2c-3 整组采集配置页面（基线87848bea）

Rules：先方案、m1独占、最小改动、真实后端权威、不push、230L0挂起。Y2仍未完成，主库061不能加载要求063的新API。页面开发与浏览器隔离验收先行，实际商城与J原Run不改。

## 产品入口

在现有同步计划编辑器增加“单路计划 / 整组采集”页签，单路为默认且原交互保留。整组组件单独加载，展示当前配置及状态/周期/12来源/当前版本；状态文案“已配置·已停用”“已启用配置”“已退役”，不能把enabled说成成功运行。当前阶段尚无Y3执行器，明确提示“执行调度尚未接通”，不显示立即运行或真实同步成功。

创建：从原assetControlClient.listInstallations与getRuntimeInstallation选择已安装实例/当前generation，调用options；缺源/歧义显示管道中文名和缺口，未ready禁保存。策略下拉仅server policies，显示易读名称，详情可查看exact引用；成员由server自动匹配，不提供任意JSON/哈希输入。周期提供每小时/每天预设及自定义，服务端最终验证。保存后disabled，页面刷新原回执及列表。已有组编辑只允许disabled；启用、停用、退役使用当前ref与独立原key，retired只读。已被其他definition占用的选项不能创建新组。

## 安全请求与待确认结果

新增api/snapshotSchedules.ts：直接使用统一tenantAuthHeaders/getApiBase，不走默认离线写队列或GET缓存、不自动重试；所有返回严格校验schema/租户/定义/状态/ref。发起前与响应后校验租户、subject、authRevision；切换后丢弃旧响应，不让旧界面覆盖新租户。只读选项不能作为服务端许可。

每次写先生成固定definitionId/key，并显式保存“待确认请求”到该tenant+subject专用浏览器本地记录（只含配置引用和请求，不含凭证/客户数据，不作为权限或业务状态）。保存失败则不发请求。该记录唯一用途是页面/电脑重启后的原key只读核对；不是离线重放队列，不会自动发送。任何网络/5xx或无法校验的成功响应保留记录，界面锁住该命令，只提供“核对原操作”；GET原receipt匹配scope/actor/definition/key/intent/expectedRef与配置参数后才清除。404表示尚未找到，不能据此自动重发或生成新key。确定4xx拒绝可清除待确认记录，仍不得自动重试。成功响应也须原receipt核对后解除待确认，避免只凭latest状态推断。待确认界面允许导出/复制原key做审计，不提供一键丢弃后重发。

按钮busy用同步ref拦双击；租户/auth事件使整组组件重建并清空前租户显示，待确认记录按scope+subject隔离。只显示当前subject记录。客户端角色提示不替代后端配置权限。

## 文件与验证

新增apps/web/src/api/snapshotSchedules.ts与snapshotSchedules.test.ts；新增apps/web/src/pages/s2/SnapshotSchedulesPanel.tsx及SnapshotSchedulesPanel.test.tsx、独立CSS；最小修改dataSchedules.tsx引入组页签，原单路测试回归。必要的解析器可拆snapshotScheduleContracts.ts并登记。无依赖新增，不触碰用户package.json/package-lock.json。

先写客户端/交互Red，再实现；验证无自动重试/无离线队列、原key核对、跨租户丢弃、缺源禁保存、初始disabled、启停CAS与双击、待确认重载不发送。跑目标vitest、类型检查/构建与浏览器验收。浏览器隔离具名API场景只验UI，不算真实源/经营验收；真实租户页面和业务验收在063克隆升级后执行，不提前宣布。后续Y2c并发锁验证与旧generation负例，Y3–Y6沿主清单继续。

## Y2c-3验证结果（2026-09-16）

已新增snapshotSchedules.ts安全客户端及SnapshotSchedulesPanel.tsx/CSS/交互测试；dataSchedules.tsx仅增加默认单路/按需加载整组页签，原单路逻辑不改。整组实例/运行代次使用原assetControlClient读取，来源和策略来自新server options；缺源/占用/策略不可用禁止保存。配置默认disabled，启用须当前选项就绪且没有未保存周期/策略修改；停用不依赖选项读取成功，退役二次提示；不存在“立即执行”假入口。

客户端请求不经过离线队列/GET缓存，无自动重试；30秒超时覆盖响应体读取，未知结果保留租户+subject专属待确认记录，写前本地记录保存失败则零请求。记录只为原key查询，不作业务/权限权威。恢复只GET原receipt，匹配scope/actor/key/intent/expectedRef/状态/前驱/版本和配置参数，匹配后才清除；再GET当前定义避免将旧操作回执状态当最新状态。切租户/authRevision丢弃旧响应；同步busy拦双击。明确4xx拒绝只清本命令记录，不清其他key。404尚未找到回执仍保留等待，不自动重发；若确实未接收的未知请求长期不存在，后续需正式服务端关闭/否决原key流程，当前不伪装恢复完成。

Red客户端模块缺失；最初环境npm不在PATH/根vitest路径不存在不算测试证据，改用已有/Users/ddt/.nvm/versions/node/v20.20.2/bin/node与apps/web/node_modules/vitest，无依赖变更。页面整合类型检查发现旧页面尾部不止BpSplit，已用fragment包含原单路全内容；按需加载避免原单路加载新控制client。StrictMode复挂载、身份切换、缺源禁保存、提交防双击与旧回执核对后刷新当前状态均已验收。

最终4个vitest文件16 passed（/tmp/aos-group-ui-final-tests-v2.log），tsc --noEmit通过（/tmp/aos-group-ui-final-types-v2.log），Vite构建通过1.96秒（/tmp/aos-group-ui-final-build.log，仅已有chunk-size建议）。git diff --check通过。

浏览器使用新无登录Chrome上下文、127.0.0.1:15174编译预览，所有API拦截为明确“隔离验收实例（非真实商城）”，禁止其他外部请求/写。脚本y2c3-ui/browser-acceptance.mjs、result.json与01–05截图保留。完整流程：缺源禁保存→模拟写已提交但响应丢失→刷新后zero resend→原key只读核对→启用→停用→退役；4个fixture写命令、liveAosRequests=0/sourceReads=0、pageerror=0。首两次脚本把role=tab误用button导致定位超时，已保留failure现场并按真实BpTabs语义修正，不修改产品行为来迁就测试。最终日志/tmp/aos-group-ui-browser-verified.log。1440桌面已目视检查；760新面板无横向溢出且编辑字段可达，外层既有侧栏在窄屏占据上方较大空间，本波未声称整个旧外壳移动体验已优化。

未升级主库061，未重载真实host，未调用真实商城或执行J原Run。UI页面功能与隔离验收不是Y2整体完成、更不是业务首链/八工作台完成。下一波Y2c-4实际双连接“归组↔单路领取”竞争、配置重启读回与跨代次旧绑定负例；之后Y3 exact definition组执行/恢复、Y4生命周期、Y5真实十二源配置、Y6观察。接通Y3/Y4后必须以服务端实际调度能力/运行结果替换页面“执行尚未接通”开发阶段提示，不允许静态字样代替运行状态。m1独占、不push、230L0继续挂起。
