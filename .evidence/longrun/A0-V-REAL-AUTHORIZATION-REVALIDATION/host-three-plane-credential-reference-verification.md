# 三身份文件引用验证

2026-09-12，基线 ead2e83f，按 host-three-plane-credential-reference-plan.md 最小修改三份实现及三份测试。受保护读取返回三身份内存 DSN；角色名和 DSN 分别互异。directory/web 与 runtime 同样优先文件且坏文件不回退；无引用旧配置仍兼容。directory 保持 read-only/repeatable-read，三者 IDLE 与原真实数据库身份权限探测保留。生产依赖构造识别文件引用，但路径本身不等于身份门通过。

独立 Host 只设置文件路径和非秘密配置，清除继承的三份 DSN 环境。检查前不 resolve 符号链接，后续连接仍由原 no-follow/owner/0600/大小约束读取。没有改租约时长、资源状态、权限、安装/审批或源调用。

验证：先红 13 failed/33 passed，涉及目录/Web 回退、身份混用、旧环境复制、symlink 绕过与依赖不构造；修复后专项 46 passed，相邻生产准备/Host/身份/目录/真实隔离 PG 合计 67 passed，无 skipped。AR2 ar2-7 1801/158/93，五类错误为空。新增静态检查与方案一致。

真实只读预检：使用原受保护身份文件和原签名根，原生产 selector 返回 RuntimeHost，serve 未调用，三个 DSN 环境均不存在。归档 host-three-plane-reference-preflight.json。此项证明实际三身份隔离预检，不能证明过期安装已经恢复。

下一步唯一进程检查后启动新 v13 Host 状态文件，观察原 disabled/fenced 实例。原资源已释放，不直接复活；继续正式 disable/卸载重装或受控恢复方案。新 Niushop 1.4 仍候选，主库 a0v_023，P01 禁用，业务闭环未完成。230 L0 挂起，不 push。
