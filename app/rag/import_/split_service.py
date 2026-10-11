from pathlib import Path
from typing import Any
from html import unescape

from app.process.import_.agent.state import ImportGraphState
from app.shared.runtime.logger import logger
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
CHUNK_SIZE = 1000
CHUNK_MIN = 400
CHUNK_MAX = 1000
# 少于400字符的块参与合并，合并后严格小于1000字符。
MERGE_SHORT_SECTIONS = True

def vaildate_get_data(state:ImportGraphState)->tuple[str,str,str]:
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
        md_content = Path(md_path).read_text(encoding="utf-8")
        state["md_content"] = md_content
    if not file_title:
        # 文件名为空
        file_title = Path(md_path).stem or "default"
        logger.warning(f"file_title为空，给默认值：{file_title}")
        state["file_title"] = file_title
    # 清洗和替换数据，统一不同的系统，换成\n
    md_content = md_content.replace("\r\n", "\n").replace("\r", "\n")
    return md_content,file_title,md_path


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
            continue
        # 是不是标题
        if not is_code and title_reg.match(line_strip):
            # 开始新标题前，保存封面内容或上一节的标题和正文。
            if current_title_lines and (current_title is None or len(current_title_lines) > 1):
                chunks.append(
                    {
                        "title":current_title,
                        "content":"\n".join(current_title_lines),
                        "file_title":file_title
                    }
                )

            if current_title and len(current_title_lines) == 1:
                current_title = current_title + "-" + line_strip
                current_title_lines = [current_title]
                continue
            current_title = line_strip
            current_title_lines = [line_strip]
        else:
            # 当前行是普通行
            current_title_lines.append(line_strip)
    # 考虑最后一行没计算的问题
    if current_title_lines:
        chunks.append(
            {
                "title": current_title,
                "content": "\n".join(current_title_lines),
                "file_title": file_title
            }
        )

    logger.info(f"已经完成了文档的切割，粗切后的数量：{len(chunks)}")
    return chunks


def _text_units(content: str, limit: int) -> list[dict[str, Any]]:
    """按段落、句子拆成小单元，无分隔符时按字符兜底，不引入重叠正文。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=limit,
        chunk_overlap=0,
        keep_separator="end",
        strip_whitespace=False,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", "、", " ", ""],
    )
    return [{"content": text} for text in splitter.split_text(content)]


def _table_as_text(table: str) -> str:
    """超长单行或复杂表格转为文本，保留单元格内容后再切分。"""
    text = re.sub(r"</tr\s*>", "\n", table, flags=re.I)
    text = re.sub(r"</(?:td|th)\s*>", "\t", text, flags=re.I)
    return unescape(re.sub(r"<[^>]+>", "", text))


def _content_units(chunk: dict[str, Any], section_index: int) -> list[dict[str, Any]]:
    """保留普通文本和表格行的顺序，表格行在输出时重新包成完整table。"""
    content = chunk.get("content") or ""
    limit = max(1, min(CHUNK_MIN, CHUNK_SIZE // 2 - 1))
    units: list[dict[str, Any]] = []
    position = 0
    table_reg = re.compile(r"<table\b[^>]*>.*?</table\s*>", re.I | re.S)
    row_reg = re.compile(r"<tr\b[^>]*>.*?</tr\s*>", re.I | re.S)

    for table_index, match in enumerate(table_reg.finditer(content)):
        units.extend(_text_units(content[position:match.start()], limit))
        table = match.group()
        opening = re.match(r"<table\b[^>]*>", table, flags=re.I).group()
        closing = re.search(r"</table\s*>$", table, flags=re.I).group()
        inner = table[len(opening):-len(closing)]
        rows = row_reg.findall(inner)
        simple_table = rows and not row_reg.sub("", inner).strip()
        if simple_table and all(len(opening + row + closing) <= limit for row in rows):
            for row in rows:
                units.append({
                    "content": row,
                    "table_key": (section_index, table_index),
                    "table_open": opening,
                    "table_close": closing,
                })
        elif len(table) <= limit:
            units.append({"content": table})
        else:
            units.extend(_text_units(_table_as_text(table), limit))
        position = match.end()

    units.extend(_text_units(content[position:], limit))
    for unit in units:
        unit["section_index"] = section_index
        unit["title"] = chunk.get("parent_title") or chunk.get("title")
    return units


def _render_units(units: list[dict[str, Any]]) -> str:
    """给跨章节内容保留原标题，给拆开的表格补齐开始、结束标签。"""
    parts: list[str] = []
    active_table = None
    table_close = ""
    previous_section = None
    for unit in units:
        table_key = unit.get("table_key")
        if table_key != active_table and active_table is not None:
            parts.append(table_close)
            active_table = None
        if previous_section is not None and previous_section != unit["section_index"]:
            parts.append("\n\n")
        if table_key is not None and active_table is None:
            parts.append(unit["table_open"])
            table_close = unit["table_close"]
            active_table = table_key
        parts.append(unit["content"])
        previous_section = unit["section_index"]
    if active_table is not None:
        parts.append(table_close)

    content = "".join(parts).strip()
    title = units[0]["title"]
    # 从章节中间开始的块补回标题；过长的标题保存在元数据中。
    if title and len(title) < CHUNK_MIN and not (
        content == title or content.startswith(title + "\n")
    ):
        content = title + "\n" + content
    return content


def _pack_chunks_by_length(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """拆分长章节，计算长度时包括标题和表格标签，优先避免过短的尾块。"""
    if not 0 < CHUNK_MIN <= CHUNK_MAX <= CHUNK_SIZE:
        raise ValueError("分块长度配置必须满足0 < CHUNK_MIN <= CHUNK_MAX <= CHUNK_SIZE")
    output: list[dict[str, Any]] = []
    # 分文件处理，不能为了凑长度把不同文件混到一块。
    start = 0
    while start < len(chunks):
        stop = start + 1
        while stop < len(chunks) and chunks[stop].get("file_title") == chunks[start].get("file_title"):
            stop += 1
        document_chunks = chunks[start:stop]
        units = [
            unit
            for section_index, chunk in enumerate(document_chunks)
            for unit in _content_units(chunk, section_index)
        ]
        count = len(units)
        # 优先减少短块数量、短缺字符数，再让长度接近范围中点。
        costs: list[tuple[int, int, int] | None] = [None] * (count + 1)
        boundaries = [0] * count
        costs[count] = (0, 0, 0)
        for left in range(count - 1, -1, -1):
            for right in range(left + 1, count + 1):
                size = len(_render_units(units[left:right]))
                if size > CHUNK_SIZE:
                    break
                tail = costs[right]
                if tail is None:
                    continue
                deficit = max(0, CHUNK_MIN - size)
                score = (
                    tail[0] + int(deficit > 0),
                    tail[1] + deficit,
                    tail[2] + (size - (CHUNK_MIN + CHUNK_SIZE) // 2) ** 2,
                )
                if costs[left] is None or score < costs[left]:
                    costs[left] = score
                    boundaries[left] = right
            if costs[left] is None:
                raise ValueError("单个内容单元超过CHUNK_SIZE，无法生成满足长度上限的分块")

        groups: list[list[dict[str, Any]]] = []
        cursor = 0
        while cursor < count:
            right = boundaries[cursor]
            groups.append(units[cursor:right])
            cursor = right

        section_uses: dict[int, int] = {}
        for group in groups:
            for section_index in dict.fromkeys(unit["section_index"] for unit in group):
                section_uses[section_index] = section_uses.get(section_index, 0) + 1
        part_counters: dict[int, int] = {}
        file_title = chunks[start].get("file_title")
        for group_index, group in enumerate(groups):
            section_indices = list(dict.fromkeys(unit["section_index"] for unit in group))
            titles = [
                document_chunks[index].get("parent_title") or document_chunks[index].get("title")
                for index in section_indices
            ]
            if len(section_indices) == 1:
                section_index = section_indices[0]
                parent_title = titles[0]
                part = part_counters.get(section_index, 0)
                part_counters[section_index] = part + 1
                title = (
                    f"{parent_title or file_title}_{part}"
                    if section_uses[section_index] > 1 else parent_title
                )
            else:
                parent_title = file_title
                part = group_index
                title = f"{file_title}_{group_index}"
            output.append({
                "file_title": file_title,
                "parent_title": parent_title,
                "title": title,
                "part": part,
                "source_titles": [title for title in titles if title],
                "content": _render_units(group),
            })
        start = stop
    return output


def _split_chunk_content(chunk: dict[str, Any]) -> list[dict[str, Any]]:
    """长块按内容边界拆分，最终长度计算包含标题和表格标签。"""
    return _pack_chunks_by_length([chunk])


def _merge_chunk_content(
    refine_chunks: list[dict[str, Any]], merge_across_sections: bool = False,
) -> list[dict[str, Any]]:
    """
    相邻块中任一块少于CHUNK_MIN时尝试合并，结果必须严格小于CHUNK_MAX。
    可选跨章节合并并保留各原标题；不修改输入字典。
    """
    normalized_chunks = [dict(chunk) for chunk in refine_chunks]
    padding_chunks_metadata(normalized_chunks)
    merged_chunks:list[dict[str,Any]] = []

    for next_chunk in normalized_chunks:
        if not merged_chunks:
            merged_chunks.append(next_chunk)
            continue

        base_chunk = merged_chunks[-1]
        parent_title = base_chunk.get("parent_title")
        is_same_section = (
            bool(parent_title)
            and parent_title == next_chunk.get("parent_title")
            and base_chunk.get("file_title") == next_chunk.get("file_title")
            and base_chunk.get("_source_section_index")
            == next_chunk.get("_source_section_index")
        )
        base_content = base_chunk.get("content") or ""
        next_content = next_chunk.get("content") or ""
        has_short_chunk = min(len(base_content), len(next_content)) < CHUNK_MIN
        same_file = base_chunk.get("file_title") == next_chunk.get("file_title")

        if not same_file or not has_short_chunk or not (is_same_section or merge_across_sections):
            merged_chunks.append(next_chunk)
            continue

        # 只在标题前缀确实存在时去掉它，避免误删正文。
        prefix = (parent_title or "") + "\n"
        next_body = (
            next_content[len(prefix):]
            if is_same_section and next_content.startswith(prefix) else next_content
        )
        separator = "\n" if is_same_section else "\n\n"
        combined_content = base_content + separator + next_body
        if len(combined_content) < CHUNK_MAX:
            base_titles = base_chunk.get("source_titles") or [base_chunk.get("parent_title")]
            next_titles = next_chunk.get("source_titles") or [next_chunk.get("parent_title")]
            base_chunk["source_titles"] = [title for title in base_titles if title]
            if not is_same_section:
                base_chunk["source_titles"].extend(title for title in next_titles if title)
                base_chunk["parent_title"] = base_chunk.get("file_title")
                base_chunk["part"] = len(merged_chunks) - 1
                base_chunk["title"] = f"{base_chunk.get('file_title')}_{len(merged_chunks) - 1}"
                base_chunk["_source_section_index"] = None
            base_chunk["content"] = combined_content
        else:
            merged_chunks.append(next_chunk)

    # 章节索引仅用于本次合并，备份JSON保留原来的字段结构。
    for chunk in merged_chunks:
        chunk.pop("_source_section_index", None)
    lengths = [len(chunk["content"]) for chunk in merged_chunks]
    logger.info(
        f"完成短Chunk合并：{len(refine_chunks)} -> {len(merged_chunks)}，"
        f"合并后长度小于{CHUNK_MAX}字符，"
        f"最终长度范围：{min(lengths, default=0)}~{max(lengths, default=0)}字符"
    )
    return merged_chunks



def refine_split_and_merge_chunks(chunks:list[dict[str,Any]]) -> list[dict[str,Any]]:
    """
    精细切割
    :param chunks:
    :return:
    """
    # 先处理超长内容，再按短块规则合并。
    refined_chunks:list[dict[str,Any]] = []
    # 循环chunks->chunk->是否超长->触发切割
    for section_index, chunk in enumerate(chunks):
        if len(chunk.get("content") or "") > CHUNK_SIZE:
            # 切割
            section_chunks = _split_chunk_content(chunk)
        else:
            # 不用切割
            section_chunks = [dict(chunk)]

        # 同名标题可能来自不同章节，不能仅凭标题文本判断是否可以合并。
        for sub_chunk in section_chunks:
            sub_chunk["_source_section_index"] = section_index
            refined_chunks.append(sub_chunk)

    logger.info(f"chunks经过超长以后向短切割处理！切割后的数量：{len(refined_chunks)}")
    # 进行切割后列表进行短合并
    refine_chunks = _merge_chunk_content(
        refined_chunks, merge_across_sections=MERGE_SHORT_SECTIONS,
    )
    # 返回最终处理结果
    return refine_chunks


def padding_chunks_metadata(chunks:list[dict[str,Any]]) -> None:
    """补齐普通块的父标题和序号，保留细切时已有的元数据。"""
    for chunk in chunks:
        chunk.setdefault("parent_title", chunk.get("title"))
        chunk.setdefault("part", 0)
    logger.info(f"完成chunks的元素补充，所属属性完整！")


def backup_chunks_json(chunks, md_path):
    """
    进行数据备份
    :param chunks:
    :param md_path:
    :return:
    """
    import json
    # 获取json path对象
    json_path_obj:Path = Path(md_path).parent / f"{Path(md_path).stem}.json"
    # 写入数据
    json_path_obj.write_text(data = json.dumps(chunks,ensure_ascii = False ,indent=4),encoding="utf-8")
    logger.info(f"完成了数据备份")


def split_document(state: ImportGraphState) -> ImportGraphState:
    """
    文档切分服务：
    1. 按标题层级做一级粗切
    2. 对超长文本做二次细切
    3. 构造 chunks 列表
    4. 回写 chunks
    """

    # 获取并校验参数
    md_content,file_title,md_path = vaildate_get_data(state)
    # 根据语义进行切割
    chunks:list[dict[str,Any]] = split_document_by_title(md_content,file_title)

    # 进行chunks的精细切割和合并
    chunks:list[dict[str,Any]] = refine_split_and_merge_chunks(chunks)
    # 备份chunks的内容
    backup_chunks_json(chunks,md_path)
    # 跟新state
    state['chunks'] = chunks
    return state
