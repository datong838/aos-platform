# AR2-7D D1 配置行修订身份施工卡

基线94faeb8e/AOS-000571，同一Task/Lease；独立只读调查确认meta_source现有复合PK和FORCE RLS，但无配置版本Owner。先补实际配置行版本身份，再接观察，不保存连接属性或秘密摘要。

## 文件与实现

- 新增 `services/aos-api/alembic/versions/ar2_010_source_configuration_revision.py`；`down_revision=ar2_009`。meta_source新增不透明UUID configuration_revision；新公共历史表data_source_configuration_revision仅含tenant/sourceId/revision/priorRevision/type/status/pluginId、安全manifest/hash及记录时间，不保存props或其hash。
- BEFORE INSERT生成新UUID；BEFORE UPDATE禁止身份重绑，props/type/status/plugin_id实变才产生新UUID，updated_at-only保持原修订。调用者不能指定/恢复修订号。AFTER实际INSERT/UPDATE才写历史，避免ON CONFLICT的候选INSERT污染history。
- 原有行仅在隔离迁移时建立当前修订身份基线，不虚构过去历史或观察时间；标明prior=null，recordedAt为建立版本身份时间。源删除后保留历史，无级联删除。历史FORCE RLS、双租户策略、不可变触发器，runtime仅SELECT，写入仅宿主源变更触发器。
- 新增 `services/aos-api/aos_api/source_configuration_revision.py`：HostTransaction内按tenant/source/revision精确读取安全manifest并重算原SQL规范hash；当前读取须同时验证meta_source指针，返回实际Owner引用DataSourceConfigurationRevision，不生成SecretRevision。读取配置属性仍由随后source adapter在同一SELECT取得props与修订，当前切片不接网络。
- 新增 `services/aos-api/tests/test_source_configuration_revision.py`：实际PG验证首次/相同upsert/实变/updated_at-only、冲突不产假history、客户端旧token/身份重绑拒绝、跨租户/只读权限/不可变、源删除历史保留、exact回读/正文和拆列漂移、非空降级拒绝。

## 边界与验收

只在本次18434临时实例的一次性数据库执行迁移，绝不升级共享或原18432。没有props或props哈希进入Evidence、Receipt或Git。配置行版本不证明vault指向的秘密版本、连接缓存或上游快照；这些缺口不得因此放行。新的历史Owner只证明版本身份，不能重建连接凭证。旧persist_source参数和返回不变，新增列不影响旧消费者。每个切片有新鲜测试/独立复核/证据提交，不push；AR2整波继续未完成。

## 独立复核补充：临时表遮蔽

触发器和修订读取器必须显式使用 public 权威表及自有函数；函数 search_path 将 pg_temp 放在末尾。同名临时历史表、meta_source 不得改变写入/读取的 Owner。先增加数据库反例验证失败，再修复，验证 public 历史增长且临时表为空。
