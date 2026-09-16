# SC4-5L6Y5F4 V：released L 到 live N 正式恢复证据

日期：2026-09-17

## 结论

`RELEASED_RUNTIME_REBUILD_TO_N_GREEN`。L 的 Policy9 与事件控制路由已在 released-only 严格负向入口下正式退役，九条业务路由随后 fence/drain/detach；L 正式卸载。电脑重启造成 M verify 中断后，M 按 deadline、资源释放和零 binding 门禁正式 reset，再由 clean N 替代并卸载。恢复独立 Runtime Host 后，N 完成 prepare、verify、configure、enable，最终为 active/ready/enabled。

## 关键身份与 Receipt

- L：`19620ea4-4a36-4cf1-a14a-8b24ee7d9fc3`，最终 uninstalled@etag6。
- Policy9 disable Receipt：`d8601861-de8e-5d0e-82c2-7cdd3b161c3b`。
- released event fence Receipt：`3c6250a3-91e7-4e94-bf73-38e4b8d16393`；shrink Receipt：`b414d479-c775-4d6e-9e8a-67bc03d5a0c0`。
- L disable operation：`9ef11747-6520-4f50-8a54-2d36f73443ce`；最终 detach Receipt：`e43b1b5c-77b7-4fc2-bb35-3cb29a9a54c2`，hash `sha256:c87738ebc3a779961d8752273e83cb9d45e8f47f797b46a5c18f1285724ed2fa`。
- M：`7810fc47-5d15-4e70-8b2a-1856b3fe0aae`；verify 在 Host 缺失时保持 accepted，deadline 后按正式 reset 回到 approved，再正式 uninstalled@etag6。三资源始终 released，无 binding、无业务执行。
- N：`d42cd39a-bc44-403b-a184-c241cae7769e`；generation `677046ff-6147-4b3b-905d-9e12964b6581`；最终 active@etag5、binding revision4/epoch3/enabled/unfenced/ready，三资源 live。
- Runtime Host PID 10115，singleton 生效，三身份凭据沿用现有 0600 文件；Host 状态只含 `org-org/dev-project`，canary=0。

## 最小实现

- `a0v_074` 只扩展 released generation 的负向 disable/fence/shrink，仍要求 exact 当前签名、Policy9、三 released resource、零在途、审批与两阶段 CAS；没有增加正向执行入口。
- `a0v_m_reinstall_recovery.py` 固定 L→M→N 身份和顺序，任何未知结果保留原 intent/result，不换 key 重发。
- 主库迁移前在克隆验证 552 表保持，再部署主库单头 `a0v_074`。

## 边界

本波只恢复可安装、可禁入、可恢复、可卸载重装的运行底座。Policy9 保持 disabled，没有自动生成 Case/Run，也没有外部发布。九路 successor 切换由后续 W 波完成。
