# 管道恢复前置：配置登记与真实构建分离

2026-09-12，m1，基线56ffae1d。承接D1只读孪生规格FR-D1-1/3/5及自然首链方案：配置存在不能代替实际数据证据。用户持续开发授权内的最小纠错；不启用Cron、不调用源、不新增权限。

## 实测与问题

org-org/dev-project正式HTTP查询pipelines/schedules/builds各0。当前Source niushop-qyh已登记并完成重启后的302表只读探测。代码审查发现POST /v1/pipelines在登记时生成SUCCEEDED lastBuild及DatasetHistory；main启动YAML映射时也制造seed-build成功。因此在恢复配置前必须修复成功语义。

## 文件及动作

- services/aos-api/aos_api/routers/wave_ext.py：登记只更新配置，初次lastBuild=null，数据集初始PENDING；已有dataset状态及构建记录原样保留，不追加构建历史。builds列表隐藏无ID或seed-build缓存，但优先展示已有持久调度记录。
- services/aos-api/aos_api/main.py：启动配置缓存不再制造SUCCEEDED；保留加载的已有数据集与管道运行状态，新数据集PENDING、lastBuild=null。
- services/aos-api/tests/test_pipeline_registration_truth.py：新增登记无构建/无历史、已有记录不覆盖、seed无运行隐藏/有持久运行替换、租户隔离。
- services/aos-api/tests/test_wave3_to_5.py：旧用例修正虚构成功的期待为未执行。

## 验证与风险

先红后绿，隔离数据库执行专项及既有R41/数据源邻接测试。验证不改变执行器真实成功写入路径。旧数据不删除或批量回写；已有非seed历史无法仅凭ID判断真假，本波不宣称完成历史清洗。此更改不等于管道可恢复/真实同步完成，后续仍须解决持久配置读取与运行图执行入口。

完成后提交证据并进入下一波：正式管道配置/图/源版本恢复合同，P01 Shop小范围首读及重启对账；禁止旧reset脚本或手工写业务对象。
