from app.process.import_.agent.state import ImportGraphState
from app.shared.runtime.logger import logger

def resolve_input_file(state: ImportGraphState) -> ImportGraphState:
    """
    入口识别服务：
    1. 校验 local_file_path
    2. 识别文件类型（PDF / Markdown）
    3. 回写 is_pdf_read_enabled / is_md_read_enabled
    4. 回写 pdf_path / md_path / file_title
    """
    local_file_path: str = state.get_local_file_path("local_ile_path")
    if not local_file_path:
        # 日志：体现错误信息，体现关键参数
        logger.error(f"local_file_pathd的参数为空，业务无法继续，提前终止")

        raise ValueError(f"local_file_pathd的参数为空，业务无法继续，提前终止")
    if local_file_path.lower().endswith(".md"):
        state["md_path"] = local_file_path
        state["is_md_read_enabled"] = True
        state["pdf_path"] = None
        state["is_pdf_read_enabled"] = False
        logger.info(f"local_file_path:{local_file_path},识别为md文件，后续跳转到node_img_md节点，state:{state}")
    elif local_file_path.lower().endswith(".pdf"):
        state["pdf_path"] = local_file_path
        state["is_pdf_read_enabled"] = True
        state["md_path"] = None
        state["is_md_read_enabled"] = False
        logger.info(f"local_file_path:{local_file_path},识别为pdf文件，后续跳转到node_pdf_md节点，state:{state}")
    else:
        logger.error(f"local_file_path:{local_file_path}既不是pdf,又不是md文件类型，请检查")
        raise TypeError
    return state