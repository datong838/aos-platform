# embeddings plugins

对齐 20 §3.1 / 方案 98 · 运行时 103。

- `embed-openai-compatible`：`POST /v1/embeddings/{id}/embed`（需 `AOS_EMBED_*` 或 `AGNES_*`）
- `rerank-cohere`：默认 501 stub
- 目录 + install KV + Host 分发；无网关不返回假向量
