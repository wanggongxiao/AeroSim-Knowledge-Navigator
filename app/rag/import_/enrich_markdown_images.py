import re

from pyexpat.errors import messages

from app.process.import_.agent.state import ImportGraphState
from pathlib import Path
from typing import Tuple

from app.rag.import_.config import SUPPORTED_IMAGE_EXTENSIONS, IMAGE_CONTEXT_SUB_CHARS
from app.shared.runtime.logger import logger,PROJECT_ROOT
from app.infra.llm.providers import llm_provider
from app.shared.runtime.load_prompt import load_prompt
from mimetypes import guess_type
import base64
from langchain_core.message import HumanMessage
from langchain_core.output_parsers import StrOutputParser

from app.shared.utils.rate_limit_utils import apply_api_rate_limit
from app.infra.object_storage.minio_gateway import minio_gateway
from minio.deleteobjects import DeleteObject

message = HumanMessage(
    content=[
        {"type": "text", "text": "请描述这张图片"},
        {
            "type": "image_url",
            "image_url": {
                "url": "https://example.com/image.png"
            },
        },
    ]
)

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

def scan_images(md_content, md_image_dir_obj) -> list[tuple[str,str,tuple[str,str]]]:
    """
    获取每张图片在md_content中的信息（图片名/图片地址/前后信息）
    :param md_content:
    :param md_image_dir_obj:
    :return:
    """
    image_info_list = []
    for image_file_obj in md_image_dir_obj.iterdir():
        if image_file_obj.suffix not in SUPPORTED_IMAGE_EXTENSIONS:
            # 不是图片
            logger.info(f"此次处理的文件：{image_file_obj}不是图片，略此次！！！")
            continue
        image_name:str = image_file_obj.name
        image_path:str = str(image_file_obj)
        # 是一张图片，图片名->md_content是否存在 ！[]（xxx）
        reg = re.compile(r"\!\[.*?\]\(.*?"+re.escape(image_name)+r".*?\)")
        search_match = reg.search(md_content)
        if not search_match:
            # 为空，没匹配到
            logger.warning(f"{image_name}没有在md_content引用，跳过，直接下一次！！！")
            continue
        # 找到有一章正常的图片
        start = search_match.start()
        end = search_match.end()
        #todo
        pre_content:str = md_content[max(0,start-IMAGE_CONTEXT_SUB_CHARS):start]
        post_content:str = md_content[end : min(end+IMAGE_CONTEXT_SUB_CHARS,len(md_content))]
        logger.debug(f"{image_name}:被引用，pre_content:{pre_content}")
        logger.debug(f"{image_name}:被引用，post_content:{post_content}")
        image_info_list.append(
            (
                image_name,
                image_path,
                (
                    pre_content,
                    post_content
                )
            )
        )
    logger.info(f"所有图片已经处理完毕")

    return image_info_list


def summarize_images(image_info_list:list[tuple[str,str,tuple[str,str]]],root_folder:str)->dict[str,str]:
    """
    调用视觉模型，识别图片的含义
    :param image_info_list:
    :return:
    """
    summarizer_image_dict:dict[str,str] = {}

    # 准备模型对象
    vision_model = llm_provider.vision_chat()
    for image_name, image_path, image_info in image_info_list:
        # 循环list数据，获取每一张图片
        image_prompt_text = load_prompt("image_summary",root_folder=root_folder,image_content=image_info)
        image_path_obj:Path = Path(image_path)
        image_base64_str:str = base64.b64encode(image_path_obj.read_bytes()).decode(encoding="utf-8")
        messages = HumanMessage(
            {
                "type" : "image_url",
                "image_ulr" : {"ulr":f"data:{guess_type(image_path)[0]};base64,{image_base64_str}"}
            },
            {
                "type":"text","text":image_prompt_text
            }
        )
        # 调用视觉模型
        chains = vision_model | StrOutputParser()
        apply_api_rate_limit()
        # 添加访问限制
        image_summary = chains.invoke([messages])
        # 拼接结果到字典中
        summarizer_image_dict[image_name] = image_summary
        logger.info(f"完成：{image_name}图像识别")
        # 循环外返回字典数据
    return summarizer_image_dict


def upload_image_get_rul(image_info_list:list[tuple[str,str,tuple[str,str]]] , stem:str)->dict[str,str]:
    """
    上传文件，并获取文件的访问url地址
    :param image_info_list:
    :param stem:
    :return:
    """
    # 删除minio中对应文件的所有图片
    image_url_dict:dict[str:str] = {}
    minio_client = minio_gateway.client()
    list_object = minio_client.list_objects(
        bucket_name=minio_gateway.bucket_name,
        prefix=minio_gateway.image_dir[1:] + "/" + stem,
        recursive=True
    )
    delete_objetc_list = [DeleteObject(obj.object_name) for obj in list_object]
    errors = minio_client.delete_objects(
        bucket_name=minio_gateway.bucket_name,
        delete_objects=delete_objetc_list
    )
    for error  in errors:
        logger.warning(f"删除图片出现问题：{error}")
    # 重写上传对应的文件
    for image_name,image_path  in image_info_list:
        try:
            minio_client.fput_object(
                bucket_name=minio_gateway.bucket_name,
                object_name=minio_gateway.image_dir+"/"+stem + "/" +image_name,#对象会决定在minio中的显示
                file_path=image_path,
                content_type=guess_type(image_path)[0]
            )
            url = minio_gateway.build_image_url(stem,image_path)
            image_url_dict[image_name] = url
            logger.debug(f"image_name:{image_name}已经完成上传")
        except Exception as e:
            logger.warning(f"{image_name}上传失败，跳过，继续上传图片！！！")
    # 记录图片和对应的反问地址
    return image_url_dict


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

    # 调用视觉模型
    summarizer_image_dict:dict= summarize_images(image_info_list,md_image_dir_obj.stem)
    image_url_dict: dict[str:str] = upload_image_get_rul(image_info_list,md_image_dir_obj.stem)
    return state