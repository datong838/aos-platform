# 最小修复方案/代码复审

原160未改；新增161仅三public journal表，预先完整验证原aos_app owner/FORCE RLS与角色/授权身份，未知表/列身份或writer宽权原子拒绝，再清runtime/PUBLIC表/列级权限显式SELECT，最终按实际有效权限核拒绝DML/列写。旧表/default ACL/策略/触发器/数据和writer原SELECT INSERT/intent.version UPDATE保持，未授Run UPDATE。禁止破坏性downgrade，不建立新执行身份。

真实PG legacy-default fixtures再执行原160产生过宽授权；runtime direct INSERT UPDATE DELETE TRUNCATE（含0匹配行）拒绝，PUBLIC/列授权收回，writer新test-only fixture写与runtime同scope1/其他org或workspace0，未知grantee与owner/RLS/writer漂移全原子拒绝。专项和原journal/原atomicwriter/原readonly reconciliation/原snapshot相邻累计80PASS0skip，实际实验集群7695416748450308141；先前tmpfs PANIC容量故障单列不算通过。

真实恢复卷未迁移/无页面代码变化，浏览器产品验收不适用代码波；当前160最新副本原迁移与161/native全数据ACL delta仍须执行，完整child及parent Task不因测试通过提前Delivery。不能以本修复开启Host/worker/Provider或替代正式身份/当前签名安装配置/八工作台及自然首链。
