from typing import TypedDict
import copy


class ImportGraphState(TypedDict):
    """
    图的状态定义，包含所有节点产生和消费的数据字段。
    TypedDict 让我们在代码中能有自动补全和类型检查。
    使用字典式访问（如 state["task_id"]、state.get("chunks")）。
    """
    task_id: str

    # --- 流程控制标记 ---
    is_md_read_enabled: bool
    is_pdf_read_enabled: bool

    # --- 路径相关 ---
    local_dir: str  # 文件夹地址  (pdf -> md  -> 输出的文件夹地址)
    local_file_path: str  # 传入文件地址 不确定md pdf
    file_title: str
    pdf_path: str  # pdf地址 文件 <- local_file_path
    md_path: str   # md地址 文件 <- local_file_path

    # --- 内容数据 ---
    md_content: str
    chunks: list
    item_name: str

    # --- 数据库相关 ---
    embeddings_content: list

graph_default_state: ImportGraphState = {
    "task_id": "",
    "is_pdf_read_enabled": False,
    "is_md_read_enabled": False,
    "local_dir": "",
    "local_file_path": "",
    "pdf_path": "",
    "md_path": "",
    "file_title": "",
    "md_content": "",
    "chunks": [],
    "item_name": "",
    "embeddings_content": [],
}

def creae_default_state(**arges) -> ImportGraphState:
    """
    创建一个state根据指定参数创建
    ：:param:可以随意传入参数，注意参数名要和state一样
    :return:state
    """
    deepcopy_new_state = copy.deepcopy(graph_default_state)
    deepcopy_new_state.update(arges)
    return deepcopy_new_state

# 获取创建好的默认的空的state
def get_default_state() -> ImportGraphState:
    return graph_default_state

# if __name__ == "__main__":
#     graph_default_state = get_default_state(task_id="007",local_file_path="./烫金机.pdf")
#     import json
#     # 打印json格式
#     print(json.dumps(graph_default_state, indent=4))