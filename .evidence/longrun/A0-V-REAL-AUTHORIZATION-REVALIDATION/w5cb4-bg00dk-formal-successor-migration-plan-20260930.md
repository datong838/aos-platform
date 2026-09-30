# W5CB4 BG00dk｜当前签名来源与 1.12 正式接入迁移计划

## 上位边界和当前事实

复习 231-2 的不可变签名/OCI/lock 及 231-3 的安装状态机、安全替换、禁入与恢复；复核 BG00ck 当前迁移备份/克隆证据。当前实例 `aos-a0v-recovery-pg-data` 在 `colima-aos-extension`，库 `aos_current_preview_20260927@a0v_118`。本波只读，没有新建 Registry/安装、当前库写入或 Host 启动。

当前受检签名 receipt 的 keyId 为 `a0v-local-ecommerce-current-v1`、trust-root revision `sha256:0a99db8b…ab95752`、growth `1.11.0` contentHash `sha256:3d8817e0…2b328`。BG00dj 新开发签名 keyId 为 `a0v-local-ecommerce-growth-1-12-v1`、trust-root revision `sha256:88b57e1d…943701e`、growth `1.12.0` contentHash `sha256:ca604f9b…6bd1`。两棵树/两把钥匙各自可核，但新钥匙不在当前 trust roots 中；开发签名不构成当前组织批准。

当前安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`：current/etag revision 3、state approved、active_revision NULL、lock revision 1/hash `sha256:b3418001…3727d`，resolved 四包中 growth 仍 1.11.0。Registry 仅四个 published 旧版本，没有 1.12.0。不得在 lock 或签名树中原位替换字节；须建立新版本、受信签名来源与新不可变 composition/安装转换，并证明旧版本和其他租户不受影响。

## 下一施工波分解与停止门

1. **独立克隆试验波**：确认当前最新 m1/权威卷/迁移；在零执行窗口作 a0v_118 新一致 custom dump + globals 私有备份，SHA/TOC/0600 验证。BG00ck 的既有备份可核，但取自 a0v_117 迁移前，不能代替本次当前基线。全库恢复到新独立容器/卷，比较安装、lock、Registry、权限及控制表行数/摘要；克隆上使用合法来源的 trust-root 更新流程和新版本 publish/锁/安装迁移合同，故障注入与回滚均按 231-3。试验不能改当前库。
2. **身份与批准来源波**：必须核组织批准的签发/信任根轮换 authority、maker/checker 分离、正式运行/目录/Web 三身份、精确 Host assignment/Owner。当前本地开发 key 仅作隔离演练，不直接提升为当前 trust root；缺合法 authority 时仅该实例继续禁入，并完成可独立代码项。
3. **配置与自然首链波**：八类配置候选的当前有效来源逐项建产品/审批/预算证据，确切绑定新 installation/generation；E16 gate/tenant/CAS/Receipt/预算权限复验后才有界启 Host。不得以全 0 候选或页面按钮当业务通过。
4. **当前切换波**：克隆全链 GREEN 后，重新生成可校验当前备份、确认 API/Web/worker/Host/Provider 零执行及无未决副作用，核对新受信签名/审批/安装来源，再以原子、可恢复步骤写当前库。未知效果只读对账，不重发；执行后逐项回读版本/lock/绑定/页面/自然结果。失败保持禁入并按已证明的恢复路径回滚。

## 不能沿用的旧脚本

`scripts/a0v_current_preview_registry_publish.py` 与 `a0v_current_preview_installation.py` 固定 growth 1.11.0、a0v_107 首装空库前提，当前 a0v_118 且已有 approved 安装，不可直接拿它们发布或迁移 1.12.0。下一波先在独立克隆上形成精确 successor 文件级方案、RED 与测试，不改写旧脚本的历史语义。
