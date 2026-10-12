"""
向量化服务模块，负责为文档切块批量生成稠密与稀疏向量。
"""
from app.shared.runtime.logger import logger, step_log
from app.infra.llm import llm_provider
from app.rag.import_.config import EMBEDDING_BATCH_SIZE
from app.process.import_.agent.state import ImportGraphState
def embed_chunks(param):
    pass


def require_chunks(state):
    pass
@step_log("embed_chunks")
def embed_chunks(chunks: list[dict], *, step: int = EMBEDDING_BATCH_SIZE) -> list[dict]:
    chunks_vector: list[dict] = []
    total = len(chunks)
    for index in range(0, total, step):
        try:
            step_chunks = chunks[index:index + step]
            vector_str_list = []
            for item in step_chunks:
                item_name = item.get("item_name")
                content = item.get("content", "")
                vector_str_list.append(f"主体:{item_name},内容:{content}" if item_name else content)
            result = llm_provider.embed_documents(vector_str_list)
            for i, chunk in enumerate(step_chunks):
                chunk_new = chunk.copy()
                chunk_new["dense_vector"] = result["dense"][i]
                chunk_new["sparse_vector"] = result["sparse"][i]
                chunks_vector.append(chunk_new)
        except Exception as exc:
            logger.warning(f"index={index}步骤,发生错误,跳过,继续生成向量!!,错误信息:{str(exc)}")
            continue
    return chunks_vector


def generate_chunk_embeddings(state: ImportGraphState) -> ImportGraphState:
    """
    向量化服务总入口
    功能：校验切块数据 → 批量生成稠密/稀疏向量 → 回写到 state
    输出：更新后的 state，包含带有 dense_vector 和 sparse_vector 的 chunks
    """
    # 先确认 chunks 存在，再批量写回 dense/sparse 向量字段
    state["chunks"] = embed_chunks(require_chunks(state))
    return state