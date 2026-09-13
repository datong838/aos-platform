# D2d-3a 受限收件与查询SQL验证

基线87ec28bf，2026-09-14，m1；迁移租约A0V-CONFIGURATION-STAGE-API-SCHEMA-20260914。新增a0v_037_configuration_stage_api.py及test_configuration_stage_api_pg.py，未部署主库。

固定NOLOGIN角色仅EXECUTE三个函数，未授配置/队列表权限。原scope/subject、非特权session、指定role与READ COMMITTED必须匹配；当前admin/asset-installer成员和当前安装标记由SQL读回。核当前composition锁及permissionDiff摘要与安装引用，Host仍做完整原授权。查询固定原租户原主体，不返回配置正文。

收件返回固定receipt，3分钟期限；同key同内容返回原记录、冲突拒绝；每租户64/每主体8未决上限由租户事务锁串行。原主体权限撤销后连旧receipt重放/查询也拒绝。配置和启用均不在API函数内执行。

验证：RED确认迁移未实现；首轮发现隔离schema未给逻辑API角色USAGE，修正测试fixture，不扩大产品权限。最终API15项+036守卫24项+原子消费者8项，共47 passed、7既有warning；diff检查通过，Alembic单头037前驱036。权限拒绝、不同subject、负租户、摘要损坏、角色撤销、owner/viewer拒绝、同键冲突、8/64容量和CAS漂移重放均覆盖。

限制：SQL测试锁记录为隔离最小列夹具，不等于当前主库完整锁与真实浏览器验收。查询目前实测pending态，成功结果关联由036和消费者测试分别验证，尚需全链集成。还未建立专用LOGIN凭据、HTTP入口、产品来源选择或实际部署。下一波次D2d-3b将固定SQL接入受保护连接与HTTP，缺凭据时明确不可用，禁止退回Host/通用Web连接；远程OpenFGA模式拒绝本地权限适配。
