# UQ5-B2b 签名页面HTTP验证

2026-09-13，m1基线2b7a060e，不push。

新增GET /v1/bundles/{publisher}/{bundle_id}/{version}/{entrypoint}，复用B2a已发布签名入口读取。资源origin与父页面origin显式配置才可用；仅packageHash/contentHash各一次。匿名接口只返回已发布静态页面代码，不提供租户数据、身份参数或执行功能。

响应使用text/html UTF-8、no-store/nosniff/no-referrer、sandbox allow-scripts、default/connect/base/form/object限制及精确frame-ancestors。内联脚本/样式来自已签名HTML，不允许外部资源或eval。异常统一脱敏，无凭据回退。Registry连接只读且不继承请求租户；路由清单与生成产物一致（550条）。

验证：真实临时签名文件贯穿读取/HTTP35 passed；连同原资源解析和发布策略68 passed，7项既有警告。涵盖成功HTML与安全头、缺配置/恶意父origin、重复/额外/缺失参数、后端/未声明HTML、读取中撤销、未知异常不泄漏。AR2阶段验证扫描1851模块，classified163/migrated93，五类错误列表均空。

限制：TestClient与Registry行替身，不是主API部署或浏览器实际CSP验收。原主库030、原RuntimeHost、旧签名包均未改；UQ6部署后需实际浏览器验收。B3立即接续growth1.8候选、固定投影方法和经营参谋签名页面。
