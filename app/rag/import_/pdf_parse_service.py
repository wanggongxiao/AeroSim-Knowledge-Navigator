from os import mkdir
from pathlib import Path
from typing import Tuple

from numpy.random.mtrand import random_sample

from app.process.import_.agent.state import ImportGraphState
from app.shared.runtime.logger import logger,PROJECT_ROOT

def vaildate_path_values(state: ImportGraphState)->Tuple[Path, Path]:
    pass
    # 获取请求参数
    local_dir = state.get('local_dir')
    pdf_path = state.get('pdf_path')
    # 非空校验Pdf_path不能为空，local_path可以为空
    if not pdf_path:
        logger.error(f"pdf_path地址为空！，业务无法继续。操作终止")
        raise ValueError(f"pdf_path地址为空！，业务无法继续。操作终止")
    if not local_dir:
        local_dir:Path = PROJECT_ROOT / "output"
        logger.warning(f"local_dir为空，不影响业务正常进行，给与默认，默认值L{str(local_dir)}")
    # 转成对应的path对象
    pdf_dir_obj:Path = Path(pdf_path)
    local_dir_obj:Path = Path(local_dir)
    # 进行文件夹和文件存在性校验
    if not pdf_dir_obj.is_file():
        logger.error(f"df_path地址为{pdf_dir_obj}，地址不存在或文件不存在，提前终止！")
        raise ValueError(f"df_path地址为{pdf_dir_obj}，地址不存在或文件不存在，提前终止！")

    if not local_dir_obj.is_dir():
        logger.error(f"local_dir地址为：{str(local_dir_obj)},不存在或者不是文件夹，创建对应文件夹，业务继续")
        local_dir.mkdir(parents=True,exist_ok=True)

    return pdf_dir_obj, local_dir_obj

def parse_pdf_to_markdown(state: ImportGraphState) -> ImportGraphState:
    """
    PDF 解析服务：
    1. 调用 MinerU
    2. 下载并解压解析结果
    3. 获取 Markdown 路径和正文内容
    4. 回写 md_path / md_content / local_dir
    """
    pdf_path_obj,locaal_dir_obj = vaildate_path_values(state)

    return state