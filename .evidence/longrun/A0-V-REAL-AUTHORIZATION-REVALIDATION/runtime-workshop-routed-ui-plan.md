# N8 按工作台路由选择签名前端的技术切片

基线 d632e11b。实际安装锁定 growth 1.7.0 七路由、operations-base 1.2.0 一路由，均没有 frontend。runtime-workshop-route-ownership.json 保存本次实际文件哈希与声明；不得原地修改已安装签名包。

## 选择

保留 7+1 包归属，避免合并成一个任意扩大 claims 的 UI。ProductionUiSessionResolver 增加可选 requested_route：不传时保留当前仅一个前端候选规则；传入时先按每个包自己声明的 navigation route 查找前端，再验证签名、Release、锁 hash、frontend manifest/artifact、该 UI 所有 routeClaims 必须是所属包自己的精确 navigation route（本工作台切片不接受通配符）。同路由多候选或不属于此包均拒绝。返回 initialRoute 使用所请求的精确路由。

该选择只返回内容资源信息，不能授予业务权限。当前安装/代次/纪元、禁入和 roles/markings 仍由 RuntimeViewReader 与随后专用目录/会话接口核验；每条 read/command 再核当前后端权限。旧 legacy catalog 谓词不改。

## 顺序及文件

1. services/aos-api/aos_api/extension_runtime/ui_resources.py 与 tests/extension_runtime/test_ui_resources.py：先实现并验证路由选择、双包互不抢路由、定义/签名漂移拒绝；旧单前端调用回归。
2. runtime_view.py 与专用工作台目录/会话接口：只从 current ready 的安装和签名工作台贡献投影目录，返回精确绑定。不能让新目录仍落入八页旧 HTTP 客户端。
3. 新版本 frontend 构建与受控 bridge 读/命令契约；增长七页及基础经营页分别归包。共用纯展示/bridge SDK 可复用，不能带主站凭据或任意 URL/SQL 调用。新包正式 Registry/Installation 交付，不覆盖现有 1.7.0/1.2.0。
4. 新宿主按路由挂载签名 ExtensionHost，安装/禁入/恢复/卸载重装后实测。首链及八真实经营场景最后验收，测试通过不等于完成。

## 并行清单的衔接（仍由 m1 单人串行）

主库仅 runtime-owner 为 admin，未找到独立审批账号；身份问题已询问用户，但不等待来停止本技术切片。正式 cutover ActionType 尚不存在：需要作为宿主控制能力正式交付并核对定义，不能为赶通链手写已批准 Proposal。当前 9 路由仍 legacy/fenced，当前 UI 无签名前端也应维持不可用，不能开放旧页面充数。
