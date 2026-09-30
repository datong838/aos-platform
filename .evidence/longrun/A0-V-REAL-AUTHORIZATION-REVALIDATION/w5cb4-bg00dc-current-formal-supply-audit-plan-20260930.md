# W5CB4 BG00dc｜当前正式 Host 与八候选来源只读审计方案

## 上位与范围

复习 231-3 安装/运行顺序、E17-s 三身份代次门、E17-u Host identity/Owner、E17-w 八候选生产者、BG00da/db 准备态禁入。只读重验当前签名、库版本、安装状态、凭据入口、Host identity/assignment、enabled binding 和八类候选；区分已存在签名制品、缺正式凭据引用、缺数据库投影、缺产品批准对象。不得读凭据正文或商城源，不写当前库，不启 Host/worker。

## 文件与判据

- 调用 `scripts/a0v_current_preview_http.py:preflight` 核签名树/四包/安装/迁移；只输出无秘密摘要。
- `scripts/a0v_current_runtime_host_preflight.py --preparation-only` 不给凭据文件，确认固定 `CREDENTIAL_FILE_REQUIRED`；不借 test-only/旧 BM 凭据做正向。
- `psycopg` 当前连接 `read_only=True` 后调用 `read_candidates` 并读 Host identity/assignment/operation/binding、enabled binding，精确 `org-org/dev-project`。
- 对照 E17-w 生产者表和当前源码，列各类候选下一合法产品入口；不把 count 或草案当正式配置授权。

## 收口

本波为审计波，无代码修改时 RED/回归不适用。verification 写可复核命令/退出码、风险与下波最小项；D-waves/01/06/续接文档及 `m1` 精确提交。若当前实例缺正式 authority，保留禁入并转独立主线研发。
