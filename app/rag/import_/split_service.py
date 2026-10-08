from pathlib import Path
from typing import Any

from app.process.import_.agent.state import ImportGraphState
from app.shared.runtime.logger import logger
import re

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
    # 清洗和替换数据，统一不同的系统，换成\n
    md_content = md_content.replace("\r\n", "\n").replace("\r", "\n")
    return md_content,file_title


def split_document_by_title(md_content:str, file_title:str)->list[dict[str,Any]]:
    """
    根据标题进行文档内容给的切割
    :param md_content:
    :param file_title:
    :return:
    """
    # 根据\n切换若干个行，看是不是标题

    # 定义存储数据的容器
    chunks:list[dict[str,Any]] = [] # 记录历史数据的整体数据，标题+行的数据库-》向量数据库
    current_title:str | None = None
    current_title_lines:list[str] = []
    is_code:bool = False
    # md_content的内容切割
    title_reg = re.compile(r"^\S*#{1,6}\s.+")
    md_content_lines = md_content.split("\n")
    for line in md_content_lines:
        line_strip:str = line.strip()
        if not line_strip:
            logger.debug(f"当前行为空行，跳过了处理！！")
            continue
        # 是否进去或者输出代码块
        if line_strip.startswith("``` ") or line_strip.startswith("```"):
            # 进入或者出去
            current_title_lines.append(line)
            is_code = not is_code
        # 是不是标题
        if not is_code and title_reg.match(line_strip):
            # 当前行是标题行
            if not current_title and len(current_title_lines) > 1:
                chunks.append(
                    {
                        "title":current_title,
                        "content":"\n".join(current_title_lines),
                        "file_title":file_title
                    }
                )

            # else:
            #     # 连续标题
            #     current_title = current_title + "-" + line_strip
            #     current_title_lines = [current_title]
            #     continue
            if current_title and len(current_title_lines) == 1:
                current_title = current_title + "-" + line_strip
                current_title_lines = [current_title]
                continue
            current_title = line_strip
            if not current_title and len(current_title_lines) > 0:
                current_title_lines.append(line_strip)
            else :
                current_title_lines = [current_title]
            current_title_lines = [line_strip]
        else:
            # 当前行是普通行
            current_title_lines.append(line_strip)
    # 考虑最后一行没计算的问题
    if len(current_title_lines) >1:
        chunks.append(
            {
                "title": current_title,
                "content": "\n".join(current_title_lines),
                "file_title": file_title
            }
        )

    logger.info(f"已经完成了文档的切割！！！！")
    return chunks


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
    # 根据语义进行切割
    chunks:list[dict[str,Any]] = split_document_by_title(md_content,file_title)
    return state