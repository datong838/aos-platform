# W5CB4 安全全栈重启隔离验收记录（2026-09-27）

## 结论

`ISOLATED_HTTP_UP / WORKSHOP_CATALOG_NOT_ACCEPTED / CURRENT_RUNTIME_FENCED`。本次只建立了可回退的隔离预览，不是当前栖月汇业务实例的完整重启，也不证明自然经营闭环。页面目录失败列为后置诊断项；不得为了让页面可点而跳过安装签名/manifest 校验。

## 对照计划 1–5

1. 操作前 `m1@232f8d01`，8080/18181 未监听；`aos_meta_head` 为 `a0v_092`，代码 head 为 `a0v_106`；旧容器 `/backup` 为空。保留两份既有用户未跟踪文件，不修改其他分支。
2. `scripts/a0v_safe_fullstack_recovery_clone.py --prepare` 在仓库外私有目录取得 repeatable-read snapshot `pg_dump -Fc`，备份 14,669,212 字节，0600。独立 `pg_restore --exit-on-error` 到新库 `aos_fullstack_preview_20260927`；恢复前后 557 张原表的行数指纹同为 `dcb73ce384939d3cdf004e019a03f06aebec96a94f85db1413a1bd81cc347eaf`。私有 `prepare.json` 保存文件 SHA-256，不提交备份或凭据。
3. 克隆独立顺序迁移 `a0v_093`–`a0v_106`，克隆版本为 `a0v_106`，迁移后 566 张表；原 557 张表指纹仍不变。私有 `clone-migration.json` 保存逐版本证据。
4. `--serve-clone` 只在 `127.0.0.1:8080` 启动单进程 HTTP，显式关闭迁移、Cron、AIP automation、Snapshot、Provider health、SSH 预建、Extension Runtime Host 和电商全部后台 worker。8080 与 8434 在监听，18181 无监听；8080 `/v1/health` 与 8434 `/api/v1/health` 均返回 200。运行期间再次只读查原库为 `a0v_092`、557 张原表指纹保持上述值。
5. 浏览器打开 `http://127.0.0.1:8434/workshop/cockpit`，显示“已安装工作台目录暂不可用”。同租户只读 GET `/v1/runtime-workshop/modules` 返回 `400 MANIFEST_INVALID`；独立只读候选源读取有 12 个 candidate，`_verify_installed_bundle` 均通过，因此故障位于后续资源/manifest/Runtime UI 校验链，尚未定位确切子条件。不能据此宣称页面或安装验收通过，也不能把校验降级成空目录。

## 风险与下一步

- 今日预览对隔离克隆的 `/v1/me` 曾触发本地 membership bootstrap；没有把“HTTP-only”误写成“克隆库零写”。原恢复库全表行数指纹无变化；尚无当前真实 Runtime / Receipt / 自然 worker 成功证明。
- 保留隔离备份和克隆供回退/只读诊断；不再扩张恢复库。当前库迁移/Runtime 解封仍需独立权威与正式波次。本波不继续死磕旧安装目录，返回 P2g30 RETURN 专属 Action exact binding 生产者主线；目录 `MANIFEST_INVALID` 与当前实例完整上线列待查。
- 本波只提交脚本和本 verification；不删除恢复介质、不改原库、不启动自然 worker、不读商城源、不重发旧 Run。
