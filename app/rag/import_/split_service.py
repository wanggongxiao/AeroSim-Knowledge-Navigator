from pathlib import Path

from app.process.import_.agent.state import ImportGraphState
from app.shared.runtime.logger import logger

def vaildate_get_data(state:ImportGraphState)->tuple[str,str]:
    """
    获取并校验参数
    :param state:
    :return:md_content,file_title
    """
    # 获取相关参数
    md_content:str = state.get("md_content")
    file_title:str = state.get("file_title")
    md_path   :str = state.get("md_path")
    # 非空校验和空值更新
    if not md_content:
        if not md_path or (not Path(md_path).is_file()):
            # md_path为空，或者不存在
            logger.error(f"md_content内容为空，md_path也为空或者没有对应的文件，业务无法继续，提前终止！！！")
            raise ValueError(f"md_content内容为空，md_path也为空或者没有对应的文件，业务无法继续，提前终止！！！")
        md_content = Path(md_path).read_text()
        state["md_content"] = md_content
    if not file_title:
        # 文件名为空
        file_title = Path(md_path).stem or "default"
        logger.warning(f"file_title为空，给默认值：{file_title}")
        state["file_title"] = file_title
    return md_content,file_title


def split_document(state: ImportGraphState) -> ImportGraphState:
    """
    文档切分服务：
    1. 按标题层级做一级粗切
    2. 对超长文本做二次细切
    3. 构造 chunks 列表
    4. 回写 chunks
    """

    # 获取并校验参数
    md_content,file_title = vaildate_get_data(state)
    return state