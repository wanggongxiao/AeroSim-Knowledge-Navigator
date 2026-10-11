from typing import Any

from pyarrow.lib import field, DataType

from app.process.import_.agent.state import ImportGraphState
from pathlib import  Path
import json
from app.shared.runtime.logger import logger
from app.infra.llm.providers import llm_provider
from config import ITEM_NAME_CONTEST_CHUNK_K,ITEM_NAME_CONTEXT_TOTAL_MAX_CHARS
from app.shared.runtime.load_prompt import  load_prompt
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from app.infra.vectorstore.milvus_gateway import milvus_gateway

def validate_and_get_data(state:ImportGraphState)->tuple[list[dict[str,Any]],str]:
    # 获取数据
    chunks:list[dict[str,Any]] = state.get("chunks")
    file_title:str = state.get("file_title")
    # 校验参数
    if not chunks:
        md_path:str = state.get("md_path")
        md_path_obj:Path = Path(md_path)
        if md_path_obj.is_file():
            json_path_obj:Path = md_path_obj.with_name((f"{md_path_obj.name}.json"))
            if json_path_obj.is_file():
                chunks = json.load(json_path_obj).read_text(encoding="utf-8")
                state["chunks"] = chunks
            else:
                logger.error(f"chunks没有值，Json备份文件不存在，抛出异常！！")
                raise ValueError(f"chunks没有值，Json备份文件不存在，抛出异常！！")
        else:
            logger.error(f"chunks没有值，同时也没有读取到对应的json备份数据，抛出异常！")
            raise ValueError(f"chunks没有值，同时也没有读取到对应的json备份数据，抛出异常！")
    if not file_title:
        md_path:str = state.get("md_path")
        md_path_obj:Path = Path(md_path)
        file_title:str = md_path_obj.name or "default_title"
        state["file_title"] = file_title
        logger.warning(f"file_title不存在，给与默认值：{file_title}")

    return chunks , file_title


def call_llm_return_item_name(chunks, file_title)->str:
    """

    :param chunks:
    :param file_title:
    :return:
    """
    # 获取模型客户端对象
    llm_model = llm_provider.chat()
    # 拼接模型对应提示词
    context = ""
    for chunk in chunks[:ITEM_NAME_CONTEST_CHUNK_K]:
        context += f"标题：{chunk.get('parent_title')}, 内容：{chunk.get('content')} \n"
    context = context[:ITEM_NAME_CONTEXT_TOTAL_MAX_CHARS]
    item_name_regcognition_prompt_text:str = load_prompt("item_name_regcognition",file_title=file_title,context=context)
    message:str = HumanMessage(
        content=item_name_regcognition_prompt_text
    )
    # 拼接执行调用和执行
    chains = llm_model | StrOutputParser()
    item_name = chains.invoke([message])
    # 判断item_name是否获取成功
    if not item_name:
        item_name = file_title
        logger.warning(f"没有识别出item_name,使用file_name兜底{file_title}")
    # 返回item_name


def padding_item_name_to_chunks(chunks, item_name):
    """
    完善chunk属性
    :param chunks:
    :param item_name:
    :return:
    """
    for chunk in chunks:
        chunk['item_name'] = item_name


@step_log("prepare_chunks_collection")
def prepare_chunks_collection() -> None:
    milvus_client = milvus_gateway.client()
    collection_name = milvus_gateway.chunks_collection
    if milvus_client.has_collection(collection_name=collection_name):
        return

    schema = milvus_client.create_schema(auto_id=True, enable_dynamic_field=True)
    schema.add_field(field_name="chunk_id", datatype=DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field(field_name="file_title", datatype=DataType.VARCHAR, max_length=512)
    schema.add_field(field_name="item_name", datatype=DataType.VARCHAR, max_length=512)
    schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=512)
    schema.add_field(field_name="parent_title", datatype=DataType.VARCHAR, max_length=512)
    schema.add_field(field_name="part", datatype=DataType.INT8)
    schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=512)
    schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=1024)
    schema.add_field(field_name="sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)

    index_params = milvus_client.prepare_index_params()
    index_params.add_index(
        field_name="dense_vector",
        index_type="AUTOINDEX",
        index_name="dense_vector_index",
        metric_type="IP",
    )
    index_params.add_index(
        field_name="sparse_vector",
        index_type="SPARSE_INVERTED_INDEX",
        index_name="sparse_vector_index",
        metric_type="IP",
        params={"inverted_index_algo": "DAAT_MAXSCORE"},
    )
    milvus_client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)


def recognize_and_index_item_name(state: ImportGraphState) -> ImportGraphState:
    """
    主体识别服务：
    1. 基于 chunks 构造上下文
    2. 调用 LLM 识别 item_name
    3. 将 item_name 回填到 state 和 chunks
    4. 同步写入主体名称索引
    """
    chunks,file_title = validate_and_get_data(state)
    item_name:str = call_llm_return_item_name(chunks,file_title)
    # 先修改chunks的数据-》item_name
    padding_item_name_to_chunks(chunks,item_name)
    # 定义向量数据库
    prepare_chunks_collection()
    return state