# AeroSim Knowledge Navigator

面向企业知识库的 RAG（检索增强生成）项目。当前仓库提供配置管理、提示词、模型能力和基础设施适配层，API 与业务流程仍在持续开发中。

## 当前能力

- 使用 BGE-M3 生成稠密向量和稀疏向量。
- 使用 BGE Reranker 对候选结果进行重排序。
- 封装 Milvus 向量检索、MongoDB 会话历史和 MinIO 对象存储。
- 通过 `app/infra` 提供 LLM、Embedding、Reranker、MinerU、Milvus、MongoDB 和 MinIO 的统一访问入口。
- 集中管理 LLM、视觉模型、MinerU 和 DashScope MCP 等外部服务配置。
- 提供文档解析、查询改写、图像摘要和答案生成等提示词模板。
- 导入图已接入 Markdown 图片处理与文档切分节点，标题切分逻辑仍在开发中。

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
| MinIO | `MINIO_ENDPOINT`、`MINIO_PUBLIC_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`、`MINIO_BUCKET_NAME` |
| MinerU | `MINERU_BASE_URL`、`MINERU_API_TOKEN` |

完整示例见 [`.env.example`](.env.example)。

### AutoDL 容器中的 MinIO

AutoDL 容器通常没有 `systemd`，请直接启动 MinIO 进程：

```bash
mkdir -p /root/minio-data
export MINIO_ROOT_USER=admin
export MINIO_ROOT_PASSWORD='请替换为强密码'
nohup minio server /root/minio-data --address ":9000" --console-address ":9001" > /root/minio.log 2>&1 &
```

应用和 MinIO 在同一个容器时，`.env` 使用 `MINIO_ENDPOINT=127.0.0.1:9000`。9001 是控制台端口，不用于 Python SDK。需要在本地查看控制台时，可以建立 SSH 隧道：

```bash
ssh -L 9001:127.0.0.1:9001 root@服务器地址 -p SSH端口
```

如果 Markdown 中的图片需要被浏览器访问，将 AutoDL 对外暴露的 API 地址填入 `MINIO_PUBLIC_ENDPOINT`；该值只用于生成图片 URL，SDK 仍然使用 `MINIO_ENDPOINT`。

`MINIO_ACCESS_KEY` 和 `MINIO_SECRET_KEY` 应与启动 MinIO 时的 `MINIO_ROOT_USER` 和 `MINIO_ROOT_PASSWORD` 一致。两项留空时，代码会自动读取后两项环境变量；如果应用和 MinIO 是在不同终端启动的，请把凭据明确写入应用的环境变量。

### IDE 解释器与环境变量

项目依赖的是 `python-dotenv`，代码中的导入名称是 `dotenv`：

```python
from dotenv import load_dotenv
```

如果 IDE 在这一行显示波浪线，请将项目解释器设置为 `.venv\\Scripts\\python.exe`，然后重新同步依赖。可以用下面的命令确认终端和项目环境使用的是同一个解释器：

```powershell
uv run python -c "import sys, dotenv; print(sys.executable); print(dotenv.__file__)"
```

不要安装名为 `dotenv` 的替代包；项目只需要 `python-dotenv`。

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

### 5. 验证导入图

```powershell
uv run python -c "from app.process.import_.agent.main_graph import import_app; print(sorted(import_app.get_graph().nodes))"
uv run python -m test.01_test_import_graph
```

第一条命令只验证图可以构建；第二条命令执行当前导入节点骨架并打印图结构。当前服务实现仍是占位逻辑，不会完成真实的外部模型或 Milvus 导入。

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
├── process/import_/      # LangGraph 导入流程与节点
├── rag/import_/          # PDF、Markdown、切分等导入服务
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

HTTP API 入口将在后续迭代中接入 `app/infra` 提供的网关与提供者。

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

`ImportGraphState` 使用 `TypedDict` 声明状态字段，它只提供类型检查和 IDE 补全，不会创建带有自定义方法的对象。运行时的状态仍然是普通 Python 字典，因此可以使用字典方法，例如 `state.get("local_dir")`；字段确定存在时也可以使用 `state["local_dir"]`。两者的区别是：键不存在时，`get` 返回 `None`（或指定的默认值），而下标访问会抛出 `KeyError`。

## 导入流程（开发中）

导入流程按以下节点处理文档：

```text
node_entry
  -> node_pdf_to_md
  -> node_md_img
  -> node_document_split
  -> node_item_name_recognition
  -> node_bge_embedding
  -> node_import_milvus
```

节点位于 `app/process/import_/agent/nodes/`，具体处理服务位于 `app/rag/import_/`。每个节点接收并返回 `ImportGraphState`，任务状态通过共享工具中的任务和 SSE 方法更新。

`app/process/import_/agent/main_graph.py` 已完成 LangGraph 图编排并导出 `import_app`。`app/rag/import_` 下的导入服务仍在实现中，完整导入流程需要继续接入 MinerU、模型和 Milvus 等外部服务。

### PDF 转 Markdown 当前进度

`app/rag/import_/pdf_parse_service.py` 已提供 PDF 路径校验、MinerU 上传、结果轮询、ZIP 下载和 Markdown 解压逻辑：

- `pdf_path` 必须指向现有 PDF 文件；未填写 `local_dir` 时默认使用项目根目录下的 `output` 文件夹。
- `local_dir` 不存在时会自动创建。
- MinerU 请求使用 `MINERU_BASE_URL`、`MINERU_API_TOKEN` 和 `MINERU_MODEL_VERSION` 配置；轮询行为由 `MINERU_POLL_TIMEOUT_SECONDS`、`MINERU_POLL_INTERVAL_SECONDS` 和 `MINERU_DOWNLOAD_TIMEOUT_SECONDS` 控制。

当前代码已覆盖申请上传地址、上传 PDF、轮询解析结果、下载 ZIP 并解压出 Markdown 文件。结果会保存到 `local_dir/<PDF文件名>/`；导入状态中的 `md_path`、`md_content` 等字段回写以及后续向量化流程仍在开发中。

### Markdown 标题切分

`node_document_split` 调用 `app/rag/import_/split_service.py`。当前代码优先读取状态中的 `md_content`，为空时尝试从 `md_path` 读取文件；`split_document_by_title` 开始按 Markdown 标题构造包含 `title`、`content`、`file_title` 的块。

这部分尚未完成：切分结果目前没有回写到 `state["chunks"]`，标题边界和空块处理也需要完善；超长块的二次切分以及后续实体提取、向量化和入库仍在开发中。

## 开发约定

- 使用 `uv` 管理依赖和运行命令，依赖版本记录在 `uv.lock`。
- 配置通过环境变量读取，新增配置时同步更新 `.env.example`。
- 不要提交 `.env`、访问密钥、模型权重和运行日志。
- 提交前检查 `git status`，确认没有将本地配置或生成文件加入版本库。

## 许可证

项目许可证尚未确定。
