# Y5c2 真实配置登记

2026-09-16，基线2f2ba390，m1单写、不push；用户已充分授权本地开发和栖月汇真实配置。先只刷新配置API，再逐项登记disabled配置；无源读取、无主库迁移、无新Run。

当前18181健康，API PID12961、独立Host PID12960。先使用原 a0v_event_complete_product_api.py check，读取私有凭据引用，原角色/租户预检；不打印凭据。确认旧API命令精确为此启动器和serve后仅TERM12961，保持Host12960。沿用原启动器、固定18181/current签名根/TWA PG；显式关闭 snapshot worker、迁移、QYH cron、AIP后台任务和第二Host。check失败或旧进程未退出则先排障，不叠加API。

API成功加载当前HEAD后，读取已有12源图/调度列表与实际路由；预览current exact再核验。仅P03–P12缺失图经PUT /v1/pipelines/{id}/graph创建，调度经POST /v1/schedules创建并固定enabled=false/ingest=null；既有P01/P02保留。每个请求先将固定ID及body/hash写入私有intent，未知响应只读原ID，不换ID重发。不接受HTTP200作为完成，原数据库独立连接读回图/调度；已有不同内容拒绝覆盖。

本波仅现有公开配置接口，无生产代码新增；编排如需新脚本，先补精确脚本路径/固定行为/测试。所有数据库SELECT为证据，禁止直接INSERT/UPDATE图、调度、Run。安装/代次漂移则重新预览；selection/control/binding仍待Y6当前窗口审批，故十二图调度齐全也不是可运行。

产物：同目录y5c2-api-registration-verification.json及本方案；docs接续/D-waves同步。主库061不变、主机Host不变、原Run/Receipt保持。Y6克隆迁移/受控部署/完整源组观察随后执行；Z旧任务、真实首链和八工作台经营验收未完成。

## 编排文件补充

新增 scripts/a0v_snapshot_disabled_registration.py，固定当前签名预览证据输入及P03–P12，公开API调用沿用已有 api()，私有intent使用原freeze函数；只实现缺失graph PUT与disabled schedule POST。先保存exact request，再API一次，再原ID数据库读回；已有intent只读回，缺失则未知拒绝，绝不再次发送。已有配置必须逐字段匹配预览（服务器附加字段允许），不同则拒绝。scope固定正租户，逐项复验J installation active/revision/lock/generation；业务运行/claim/input计数前后核对。新增 services/aos-api/tests/test_snapshot_disabled_registration.py 验证首次写入、未知响应后同intent读回、未知无记录不重发、冲突拒绝、写前已落intent。源读取和启用无入口。

## 实际登记发现与顺序修正

18:23 首次 P03 graph 已按原 API 落库 revision=1；schedule 返回503并独立读回无行，编排立即停止。PG原日志 2026-09-16 10:23:32.861 UTC PID723514 明确 ERROR foreign key fk_meta_schedule_pipeline_ti4d7，因此这是确定的事务拒绝，不是已提交但未知。原因：Phase5 graph 不创建 meta_pipeline；遗漏正式 pipeline/dataset 配置入口。修正顺序为 POST /v1/pipelines（原 PipelineIn，固定 sourceId/target/datasetRid/objectTypeHint/name）→原 meta_pipeline/meta_dataset 双读回→PUT graph→disabled schedule。对P03原graph仅读回不覆盖。

原P03 schedule intent保留；只为这个有PG明确外键拒绝的同ID同body请求记录 rejected-fk receipt，允许修复前置配置后第二次尝试一次，单独冻结 retry-after-fk intent。无该具体拒绝证据的任何unknown仍不重发。其余9路首试。此次为编排顺序错误，不改变数据库FK或伪造pipeline行。pipeline API现有 _persist_safe 不保证提交，编排必须独立核验pipeline与dataset两行；任何不一致停止，不能依据其200继续。

## 最终验证

当前受控API PID61700（加载2f2ba390），18181健康；Host12960未重启，新增worker关闭。P03–P12原pipeline/dataset接口、graph接口、schedule接口登记完成；独立主库读回12 pipelines/12 graphs/12 schedules/0 enabled。P01/P02图均保持revision1。源运行11、source claims10前后完全一致，主库仍a0v_061。

首次P03 schedule因FK明确拒绝保留原intent/rejected-fk/retry-after-fk三份私有记录；P03原graph读回零重写。其余9路按正确顺序首次登记。最终再次运行同一编排，30项pipeline/graph/schedule全部submitted=false，只有读回；首次结果保存在y5c2-api-registration-first-verification.json，复核结果y5c2-api-registration-verification.json。原preview只刷新observedAt，previewHash保持不变。新4项未知响应/冲突测试加preview9项共13 passed / 3.52s。

边界：这完成十二路基础配置落库，不是十二路当前selection/control/binding已审批，更不是完整源组或经营首链完成。后续先Y6a克隆库062–066迁移及保全验证，然后Y6b主库受控升级；Y5d十二路选择/控制/绑定共同窗口审批与组配置在实际执行准备时完成，以避免窗口提前过期。顺序调整只移动部署依赖，不删除Y5d退出条件。Z原业务Run处置、完整经营闭环和八工作台观察仍未完成。
