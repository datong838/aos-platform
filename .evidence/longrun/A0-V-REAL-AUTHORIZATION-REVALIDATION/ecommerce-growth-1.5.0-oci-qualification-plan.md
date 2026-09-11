# Ecommerce growth 1.5.0 OCI build / qualification 方案

日期：2026-09-12

## 固定执行参数

- Git HEAD：`50a61775`
- Docker context：`colima-aos-extension`
- Platform：`linux/arm64`（engine 实测 linux/aarch64）
- 临时 Registry 端口：`18436`
- 仓外输出：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260912/builds/ecommerce-runtime-1.5.0-v1`
- build Receipt：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260912/logs/ecommerce-runtime-1.5.0-build-v1.json`
- qualification Receipt：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260912/logs/ecommerce-runtime-1.5.0-qualification-v1.json`

## 军规与停止规则

1. build 只使用已验证具备 userns/seccomp 的隔离 context；输出必须在仓外且开始前不存在。
2. 只执行一次主 build。若调用超时或连接中断，先查 build Receipt、output tree、临时 Registry 容器和镜像，
   未确认失败前不重跑；同阶段确认失败两次则停止外部动作并审计。
3. build 只允许本地镜像与临时 Registry side effects；Receipt 的 Registry publish、Installation mutation、
   Provider invocation、external publication 必须全为 0。
4. qualification 必须读取 exact build Receipt、校验当前 Git HEAD/output tree/content/image identities，使用
   ephemeral signing root，结束后不得持久化 signature。
5. qualification 必须覆盖 image index bytes/digest、dependency lock、SBOM、backend、schema compatibility、
   schema requirements 七类 tamper rejection。
6. 本波不连接真实 Registry 数据库、不创建 Composition/Installation、不启动 runtime host、不调用 Provider。

## 退出条件与下一波

BUILD_GREEN 与 QUALIFICATION_GREEN 均落 Receipt；resolved growth 为 1.5.0，3 个 runtime admission、8 modules、
schema requirements、七类 tamper rejection 和零业务 effects 通过；清理临时 Registry 容器，记录镜像/内容/
输出 hash，closure 和独立提交。下一波准备 current trust-root 下的持久签名与 Registry draft/validate/publish
命令，但在实际写 Registry 前先完成 exact tenant、actor、Receipt 与回滚计划。
