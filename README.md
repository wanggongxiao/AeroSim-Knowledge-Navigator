# AeroSim Knowledge Navigator

面向企业知识库的 RAG（检索增强生成）项目。当前仓库提供配置管理、提示词、模型能力和基础设施适配层，API 与业务流程仍在持续开发中。

## 当前能力

- 使用 BGE-M3 生成稠密向量和稀疏向量。
- 使用 BGE Reranker 对候选结果进行重排序。
- 封装 Milvus 向量检索、MongoDB 会话历史和 MinIO 对象存储。
- 通过 `app/infra` 提供 LLM、Embedding、Reranker、MinerU、Milvus、MongoDB 和 MinIO 的统一访问入口。
- 集中管理 LLM、视觉模型、MinerU 和 DashScope MCP 等外部服务配置。
- 提供文档解析、查询改写、图像摘要和答案生成等提示词模板。

## 环境要求

- Python 3.11 或更高版本
- [uv](https://docs.astral.sh/uv/)
- 可访问的 LLM 服务（OpenAI 兼容接口）
- 按需准备 Milvus、MongoDB、MinIO 和 MinerU 服务
- 使用本地 Embedding/Reranker 模型时，需要足够的磁盘空间和内存；GPU 环境可在 `.env` 中配置设备

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 创建本地配置

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS/Linux：

```bash
cp .env.example .env
```

编辑 `.env`，至少填写 LLM 服务、模型路径以及实际使用的基础设施地址。`.env` 包含密钥等敏感信息，不要提交到 Git。

配置项按用途分为：

| 类别 | 主要变量 |
| --- | --- |
| 应用 | `APP_ENV`、`APP_HOST`、`IMPORT_APP_PORT`、`QUERY_APP_PORT` |
| LLM/VL | `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`LLM_DEFAULT_MODEL`、`VL_MODEL` |
| Embedding | `BGE_M3_PATH`、`BGE_M3`、`BGE_DEVICE`、`BGE_FP16` |
| Reranker | `BGE_RERANKER_LARGE`、`BGE_RERANKER_DEVICE`、`BGE_RERANKER_FP16` |
| Milvus | `MILVUS_URL`、`CHUNKS_COLLECTION`、`ENTITY_NAME_COLLECTION`、`ITEM_NAME_COLLECTION` |
| MongoDB | `MONGO_URL`、`MONGO_DB_NAME` |
| MinIO | `MINIO_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`、`MINIO_BUCKET_NAME` |
| MinerU | `MINERU_BASE_URL`、`MINERU_API_TOKEN` |

完整示例见 [`.env.example`](.env.example)。

### 3. 准备模型

将 `BGE_M3_PATH` 和 `BGE_RERANKER_LARGE` 指向本地模型目录。仓库提供了 ModelScope 下载脚本：

```bash
uv run python app/shared/tool/tool/download_bgem3.py
uv run python app/shared/tool/tool/download_reranker.py
```

运行前请检查脚本中的缓存目录，并根据本机环境调整路径；下载大型模型可能需要较长时间。

### 4. 验证环境变量

```bash
uv run python test/01_env_test.py
```

该命令会读取 `.env` 并输出 `BGE_M3_PATH`。当前仓库尚未提供统一的 HTTP API 启动入口，导入服务和查询服务的入口会在业务编排模块完善后补充。

## 目录结构

```text
app/
├── infra/               # 基础设施适配层
│   ├── config/          # 聚合应用与外部服务配置
│   ├── document_parse/  # MinerU 文档解析网关
│   ├── llm/             # LLM、Embedding 和 Reranker 提供者
│   ├── object_storage/  # MinIO 对象存储网关
│   ├── persistence/     # MongoDB 会话历史仓储
│   └── vectorstore/     # Milvus 向量检索网关
├── resources/prompts/   # LLM、查询改写和图像处理提示词
└── shared/
    ├── config/          # 环境变量与服务配置
    ├── runtime/         # 日志、提示词加载等运行时能力
    └── tool/
        ├── clients/     # Milvus、MongoDB、MinIO 客户端
        ├── model/       # Embedding 与 Reranker
        ├── tool/        # 模型下载等脚本
        └── utils/       # SSE、限流、任务和格式化工具
test/                    # 环境与功能验证脚本
doc/                     # 项目文档
```

业务编排目录和 HTTP API 入口将在后续迭代中接入 `app/infra` 提供的网关与提供者。

## 导入流程状态

导入流程使用 `ImportGraphState` 保存任务、文件路径、解析结果和向量化结果。通过 `get_default_state` 创建独立状态副本，并传入初始字段：

```python
from app.process.import_.agent.state import get_default_state

state = get_default_state(
    task_id="007",
    local_file_path="./烫金机.pdf",
)
```

状态工厂会深拷贝默认值，多个任务之间不会共享 `chunks` 或 `embeddings_content` 等列表字段。

## 开发约定

- 使用 `uv` 管理依赖和运行命令，依赖版本记录在 `uv.lock`。
- 配置通过环境变量读取，新增配置时同步更新 `.env.example`。
- 不要提交 `.env`、访问密钥、模型权重和运行日志。
- 提交前检查 `git status`，确认没有将本地配置或生成文件加入版本库。

## 许可证

项目许可证尚未确定。
