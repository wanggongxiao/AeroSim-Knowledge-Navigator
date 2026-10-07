from app.process.import_.agent.state import ImportGraphState
from pathlib import Path
from typing import Tuple

from app.rag.import_.config import SUPPORTED_IMAGE_EXTENSIONS
from app.shared.runtime.logger import logger,PROJECT_ROOT

def vaildate_and_data(state:ImportGraphState)->Tuple[Path, Path,str]:

    """
    获取必备的参数
        md_path_obj  ->后续获取文件
        md_image_dir_obj -> 获取图片的具体信息
        md_content ->获取没有处理的md内容
    :param state:
    :return:
    """
    # 获取参数md_path:str
    md_path:Path = state.get("md_path")
    # 非空校验
    if not md_path:
        logger.error(f"md_path变量为空，业务无法继续进行，提前终止！")
        raise ValueError(f"md_path变量为空，业务无法继续进行，提前终止！")
    # 存在校验
    md_path_obj:Path = Path(md_path)
    if not md_path_obj.is_file():
        logger.error(f"md_path变量{md_path},但没有具体的文件，业务无法继续，提前终止！！！")
        raise FileNotFoundError(f"md_path变量{md_path},但没有具体的文件，业务无法继续，提前终止！！！")
    # 读取文件md_content
    md_content:str = md_path_obj.read_text(encoding="utf-8")
    state["md_content"] = md_content
    # 获取md对应images文件地址
    md_image_dir:Path =  md_path_obj.parent / "images"
    # 返回参数
    return md_path, md_image_dir, md_content

def scan_images(md_content,md_image_dir_obj) -> list[tuple[str,str,tuple[str,str]]]:
    """
    获取每张图片在md_content中的信息（图片名/图片地址/前后信息）
    :param md_content:
    :param md_image_dir_obj:
    :return:
    """
    for image_file_obj in md_image_dir_obj.iterdir():
        if image_file_obj.suffix not in SUPPORTED_IMAGE_EXTENSIONS:
            # 不是图片
            logger.info(f"此次处理的文件：{image_file_obj}不是图片，略此次！！！")
            continue
        

    pass
def enrich_markdown_images(state: ImportGraphState) -> ImportGraphState:
    """
    Markdown 图片增强服务：
    1. 扫描 Markdown 中的图片
    2. 调用多模态模型生成图片说明
    3. 上传图片到 MinIO
    4. 替换 Markdown 图片地址并回写 md_content
    """
    # 获取和校验参数
    m_path_obj,md_image_dir_obj,md_content = vaildate_and_data(state)
    # 校验是否有图片
    # 空文件夹
    if (not md_image_dir_obj.is_dir()) or len(list(md_image_dir_obj.iterdir())) == 0:
        logger.info(f"在此目录下：{md_image_dir_obj}没有图片，无需单独处理！！")
        return state
    # 获取图片中的上下文
    image_info_list:list[tuple[str,str,tuple[str,str]]] = scan_images(md_content,md_image_dir_obj)
    return state