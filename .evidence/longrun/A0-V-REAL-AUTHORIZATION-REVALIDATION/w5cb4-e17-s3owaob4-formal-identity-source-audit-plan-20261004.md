# E17-s3o-w-ao-b4｜当前正式身份来源与切换前置只读核验方案

## 上位合同与现状

已复习 231 主计划、231-4 真实库迁移边界、AIP-7 22、BIND-1 31、2026-10-04 D-wave 与续接645。b3 仅证实不同卷的全库克隆可事务建立/回滚 test-only Reader；当前原库正式 Reader/issuer 为0。当前库仍只读，Host/worker/Provider关闭，首链 pending。

## 文件级清单

1. 仅读生产组合/正式 API 与 Host 预检源码、当前配置变量**名称和文件元数据**、权威库角色/assignment/配置计数、运行进程，不读取凭据内容或商城源。把正式 Reader、issuer、OIDC/API、Host 三身份逐项归因于可校验来源；test-only 文件单列排除。
2. 对当前角色切换的零执行窗口、新切前备份/独立全库恢复、精确授权、安装/Receipt 不变四项做可复核门表。缺门即停止本实例 DDL，保留 b3 克隆成果。
3. 独立评估 D-wave 已登记 Provider/Tool 来源候选，选择不依赖缺失正式身份的下一研发文件；本波只读审计，无代码/页面改动，浏览器不适用。
4. verification 落盘、m1 精确提交，再同步 D-wave、01/06、Authority 与 Prime；首链状态不因审计改变。

## 禁入

不导出/打印秘密，不取 test-only 账号作正式身份，不对原库写，不启 Host/worker/Provider，不读商城源、不重放旧12 Run、不手工 run_definition、不碰230 L0、不 push。
