import shutil
import time
from http.client import responses
from os import mkdir
from pathlib import Path
from typing import Tuple

import requests
from numpy.random.mtrand import random_sample

from app.process.import_.agent.state import ImportGraphState
from app.shared.runtime.logger import logger,PROJECT_ROOT
from app.infra.config.providers import infra_config
from app.rag.import_.config import (
    MINERU_MODEL_VERSION,
    MINERU_DOWNLOAD_TIMEOUT_SECONDS,
    MINERU_POLL_INTERVAL_SECONDS,
    MINERU_POLL_TIMEOUT_SECONDS,
)

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
        local_dir_obj.mkdir(parents=True, exist_ok=True)

    return pdf_dir_obj, local_dir_obj
def update_pdf_and_poll(pdf_path_obj:Path)->str:
    # 先发起请求
    token = infra_config.mineru.api_key
    url = f"{infra_config.mineru.base_url}/file-urls/batch"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    # data->请求体，参数由服务器决定的
    data = {
        "files":[
            {"name":f"{pdf_path_obj.name}", "path_id":f"{pdf_path_obj.stem}"}
        ],
        "model_version":MINERU_MODEL_VERSION
    }

    # 批量申请地址
    responses = requests.post(url=url, headers=headers, json=data,timeout=30)

    # 获取申请的结果
    status_code = responses.status_code
    if status_code != 200:
        logger.error(f"向：{url}申请文件上传地址，请求失败，状态为：{status_code}，业务无法继续！")
        raise RuntimeError(f"向：{url}申请文件上传地址，请求失败，状态为：{status_code}，业务无法继续！")
    # 获取响应数据 1.校验状态码，业务校验，获取数据
    response_dict = responses.json()
    code = response_dict.get('code')
    mes = response_dict.get('message')
    if code != 0:
        logger.error(f"向：{url}申请文件上传地址，业务失败，code为：{code}，错误信息：{mes}，业务无法继续！")
        raise RuntimeError(f"向：{url}申请文件上传地址，业务失败，code为：{code}，错误信息：{mes}，业务无法继续！")

    # rodo 网络正常，业务正常
    upload_file_urls:list[str] = response_dict.get('data',{}).get('file_urls',[])
    batch_id = response_dict.get('data',{}).get('batch_id') #用于轮询获取本次上传解析的结果

    # 判断
    if not upload_file_urls:
        logger.error(f"向：{url}申请文件上传地址，业务失败，,没有返回上传地址，业务无法继续！")
        raise RuntimeError(f"向：{url}申请文件上传地址，业务失败，,没有返回上传地址，业务无法继续！")
    if not batch_id:
        logger.error(f"向：{url}申请文件上传地址，业务失败，,没有批量表示，无法获取解析结果，业务无法继续！")
        raise RuntimeError(f"向：{url}申请文件上传地址，业务失败，,没有批量表示，无法获取解析结果，业务无法继续！")

    """
    pdf_path_obj文件对象 /文件地址
    
    """
    file_data = pdf_path_obj.read_bytes()
    upload_file_url = upload_file_urls[0]
    logger.info(f"申请文件解析地址成功！batc_id:{batch_id},地址为：{upload_file_url}")
    # upload_response = requests.put(url=upload_file_url, headers=headers, data=file_data,timeout=30)
    with requests.Session() as session:
        # 不信任系统环境
        session.trust_env = False
        upload_response = session.put(url=upload_file_url,data=file_data,timeout=30)
        upload_status_code = upload_response.status_code
        if upload_status_code != 200:
            logger.error(f"向：{upload_file_url}上传文件，网络失败，status_code:{upload_status_code},业务无法继续，提前终止")
            raise RuntimeError(f"向：{upload_file_url}上传文件，网络失败，status_code:{upload_status_code},业务无法继续，提前终止")
    logger.info(f"向指定url:{upload_file_url}文件上传成功,上传文件名：{pdf_path_obj.name}上传成功！！")
    # 轮询获取结果
    max_wait_time = MINERU_POLL_TIMEOUT_SECONDS
    poll_wait_time = MINERU_POLL_INTERVAL_SECONDS
    start_time = time.time()
    while True:
        # 先判断是否超过了最大的等待时间
        if time.time() - start_time > max_wait_time:
            logger.error(f"向batch_id:{batch_id}轮询获取返回结果，等待时间超时！业务提前终止！")
            raise TimeoutError(f"向batch_id:{batch_id}轮询获取返回结果，等待时间超时！业务提前终止！")
        # 向minerU获取解析结果
        poll_url = f"{infra_config.mineru.base_url}/extract-results/batch/{batch_id}"
        try:
            # 网络请求报错
            poll_response = requests.get(url=poll_url,headers=headers, timeout=30)
        except Exception as e:
            logger.warning(f"网络出现异常，等待下批次轮询！")
            time.sleep(poll_wait_time)
            continue

        # 判断解析结果是否正常
        # Http协议状态吗是否正常
        poll_response_code = poll_response.status_code
        if poll_response_code != 200:
            if 500 <= poll_response_code < 600:
                # 重试
                logger.warning(f"向batch_id:{batch_id}轮询获取返回结果，网络异常，状态码为：{poll_response_code},等待后，再重试")
                time.sleep(poll_wait_time)
                continue
            else:
                logger.error(f"向batch_id:{batch_id}轮询获取返回结果，网络异常，状态码为：{poll_response_code},无法继续，终止业务！")
                raise RuntimeError(f"向batch_id:{batch_id}轮询获取返回结果，网络异常，状态码为：{poll_response_code},无法继续，终止业务！")

        poll_response_dict = poll_response.json()
        poll_code = poll_response_dict.get("code", -1)
        if poll_code != 0:
            message = poll_response_dict.get("msg", "unknown error")
            raise RuntimeError(
                f"batch_id:{batch_id}轮询失败，code={poll_code}，message={message}"
            )

        extract_results = poll_response_dict.get("data", {}).get("extract_result", [])
        logger.info(
            f"batch_id:{batch_id}轮询响应："
            f"http_status={poll_response_code}, code={poll_code}, "
            f"extract_count={len(extract_results)}, "
            f"states={[item.get('state') for item in extract_results]}"
        )
        if not extract_results:
            logger.info(f"batch_id:{batch_id}未返回extract_result，等待下一次轮询")
            time.sleep(poll_wait_time)
            continue

        result = extract_results[0]
        state = result.get("state")
        if state == "done":
            full_zip_url = result.get("full_zip_url")
            if not full_zip_url:
                raise RuntimeError(f"batch_id:{batch_id}解析完成，但响应中没有full_zip_url")
            logger.info(f"batch_id:{batch_id}文件解析完成")
            return full_zip_url
        if state == "failed":
            raise RuntimeError(
                f"batch_id:{batch_id}文档解析失败：{result.get('err_msg', '')}"
            )

        time.sleep(poll_wait_time)


def download_parse_result(zip_url: str, output_dir: Path, file_stem: str) -> Path:
    """Download MinerU's ZIP result to the local output directory."""
    zip_path = output_dir / f"{file_stem}_mineru.zip"
    try:
        with requests.get(
            zip_url,
            stream=True,
            timeout=MINERU_DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            response.raise_for_status()
            with zip_path.open("wb") as output_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output_file.write(chunk)
    except Exception:
        zip_path.unlink(missing_ok=True)
        raise

    logger.info(f"MinerU解析结果已下载：{zip_path}")
    return zip_path
def download_and_extract_markdown(zip_url:str, local_dir_obj:Path,stem:str)->Path:
    # 根据zip_url地址下载对应压缩文件
    response = requests.get(url=zip_url,timeout=MINERU_DOWNLOAD_TIMEOUT_SECONDS)
    if response.status_code != 200:
        logger.error(f"{zip_url}地址无法下载资源，业务无法进行，提前终止！！")
        raise RuntimeError(f"{zip_url}地址无法下载资源，业务无法进行，提前终止！！")

    # 写入文件
    zip_file_obj:Path = local_dir_obj / f"{stem}.zip"
    zip_file_obj.write_bytes(response.content)
    # 解压到同名的文件夹中,如果存在先清空再创建
    zip_dir_obj:Path = local_dir_obj /stem
    logger.info(f"zip_dir_obj:{zip_dir_obj}")
    logger.info(f"zip_file_obj:{zip_file_obj}")
    if zip_dir_obj.is_file():
        # 清空文件夹
        shutil.rmtree(zip_file_obj)
        # 解压文件夹
    zip_dir_obj.mkdir(parents=True, exist_ok=True)
    # 解压文件夹到指定文件夹
    shutil.unpack_archive(zip_file_obj,zip_dir_obj)
    # 检查文件夹中是否有.md文件
    md_file_list:list[Path] = list(zip_dir_obj.rglob("*.md"))
    if not md_file_list:
        # 没有检查出.md文件
        logger.error(f"{zip_url}地址下载成功，解压完成，但没有md文件！业务无法继续进行，提前终止")
        raise RuntimeError(f"{zip_url}地址下载成功，解压完成，但没有md文件！业务无法继续进行，提前终止")
    for md_file_obj in md_file_list:
        if md_file_obj.stem == f"{stem}":
            logger.info(f"文件下载成功，解压成功，返回对应地址{md_file_obj}")
            return md_file_obj

    full_md_file_obj:Path = None
    for md_file_obj in md_file_list:
        if md_file_obj.stem == "full":
            logger.info(f"文件下载成功，返回的文件full.md,修改名字！")
            full_md_file_obj = md_file_obj
            break

    full_md_file_obj.rename(full_md_file_obj.with_name(f"{stem}.md"))
    return full_md_file_obj





def parse_pdf_to_markdown(state: ImportGraphState) -> ImportGraphState:
    """
    PDF 解析服务：
    1. 调用 MinerU
    2. 下载并解压解析结果
    3. 获取 Markdown 路径和正文内容
    4. 回写 md_path / md_content / local_dir
    """
    pdf_path_obj, local_dir_obj = vaildate_path_values(state)
    zip_url = update_pdf_and_poll(pdf_path_obj)
    # zip_path = download_parse_result(zip_url, local_dir_obj, pdf_path_obj.stem)
    # print(zip_path)
    # 下载并解压md文件
    md_path:Path = download_and_extract_markdown(zip_url, local_dir_obj,pdf_path_obj.stem)
    return state
