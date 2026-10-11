"""文档块合并回归测试，只调用本地切分函数，不请求模型或MinIO。"""

import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.import_.split_service import (
    _merge_chunk_content,
    padding_chunks_metadata,
    refine_split_and_merge_chunks,
    split_document,
    split_document_by_title,
)


class ChunkMergeTests(unittest.TestCase):
    @staticmethod
    def chunk(body: str, title: str = "# A", **metadata) -> dict:
        return {
            "title": title,
            "content": title + "\n" + body,
            "file_title": "manual",
            **metadata,
        }

    def test_short_chunks_merge_without_losing_text_or_mutating_input(self):
        chunks = [self.chunk("first"), self.chunk("second"), self.chunk("third")]
        original = copy.deepcopy(chunks)

        result = _merge_chunk_content(chunks)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["content"], "# A\nfirst\nsecond\nthird")
        self.assertEqual(result[0]["parent_title"], "# A")
        self.assertEqual(result[0]["part"], 0)
        self.assertEqual(chunks, original)

    def test_short_tail_merges_into_longer_previous_chunk(self):
        result = _merge_chunk_content([self.chunk("A" * 450), self.chunk("tail")])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["content"], "# A\n" + "A" * 450 + "\ntail")

    def test_merge_limit_includes_inserted_newline(self):
        with self.subTest("999 characters may merge"):
            result = _merge_chunk_content([self.chunk("A" * 600), self.chunk("B" * 394)])
            self.assertEqual(len(result), 1)
            self.assertEqual(len(result[0]["content"]), 999)

        with self.subTest("1000 characters must remain separate"):
            chunks = [self.chunk("A" * 600), self.chunk("B" * 395)]
            result = _merge_chunk_content(chunks)
            self.assertEqual(len(result), 2)
            self.assertEqual([c["content"] for c in result], [c["content"] for c in chunks])

    def test_distinct_parent_titles_and_files_remain_separate(self):
        for next_chunk in (
            self.chunk("second", title="# B"),
            self.chunk("second", file_title="other manual"),
        ):
            with self.subTest(next_chunk=next_chunk):
                result = _merge_chunk_content([self.chunk("first"), next_chunk])
                self.assertEqual(len(result), 2)
                self.assertEqual(result[1]["content"], next_chunk["content"])

    def test_distinct_original_sections_retain_both_headings_when_merged(self):
        md = "# Same\nfirst section\n# Same\nsecond section"
        chunks = split_document_by_title(md, "manual")
        original = copy.deepcopy(chunks)

        result = refine_split_and_merge_chunks(chunks)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["content"], "# Same\nfirst section\n\n# Same\nsecond section")
        self.assertEqual(result[0]["source_titles"], ["# Same", "# Same"])
        self.assertTrue(all("_source_section_index" not in c for c in result))
        self.assertEqual(chunks, original)

    def test_chunks_at_least_400_characters_do_not_merge(self):
        chunks = [self.chunk("A" * 396), self.chunk("B" * 397)]

        result = refine_split_and_merge_chunks(chunks)

        self.assertEqual([len(c["content"]) for c in result], [400, 401])

    def test_different_files_do_not_merge_even_when_cross_section_merge_is_enabled(self):
        chunks = [self.chunk("first"), self.chunk("second", file_title="other manual")]

        result = _merge_chunk_content(chunks, merge_across_sections=True)

        self.assertEqual(len(result), 2)

    def test_short_chunk_merges_with_right_neighbor_if_left_would_exceed_limit(self):
        chunks = [
            self.chunk("A" * 950),
            self.chunk("B" * 100, title="# B"),
            self.chunk("C" * 450, title="# C"),
        ]

        result = refine_split_and_merge_chunks(chunks)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["content"], chunks[0]["content"])
        self.assertEqual(result[1]["content"], chunks[1]["content"] + "\n\n" + chunks[2]["content"])

    def test_short_chunk_stays_separate_when_neither_neighbor_fits(self):
        chunks = [
            self.chunk("A" * 950),
            self.chunk("B" * 100, title="# B"),
            self.chunk("C" * 950, title="# C"),
        ]

        result = refine_split_and_merge_chunks(chunks)

        self.assertEqual([c["content"] for c in result], [c["content"] for c in chunks])

    def test_missing_title_prefix_does_not_strip_body(self):
        next_chunk = self.chunk("unused", parent_title="# A")
        next_chunk["content"] = "body without heading"

        result = _merge_chunk_content([self.chunk("first"), next_chunk])

        self.assertEqual(result[0]["content"], "# A\nfirst\nbody without heading")

    def test_existing_parent_title_and_part_are_preserved(self):
        chunks = [
            self.chunk("first", title="# A_2", parent_title="# A", part=2),
            self.chunk("second", title="# A_3", parent_title="# A", part=3),
        ]
        for chunk, body in zip(chunks, ("first", "second")):
            chunk["content"] = "# A\n" + body

        result = _merge_chunk_content(chunks)
        padding_chunks_metadata(result)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["parent_title"], "# A")
        self.assertEqual(result[0]["part"], 2)
        self.assertEqual(result[0]["title"], "# A_2")
        self.assertEqual(result[0]["content"], "# A\nfirst\nsecond")

    def test_empty_single_and_untitled_chunks_are_retained_correctly(self):
        self.assertEqual(_merge_chunk_content([]), [])
        self.assertEqual(len(_merge_chunk_content([self.chunk("only")])), 1)
        chunks = [
            {"title": None, "content": "cover", "file_title": "manual"},
            self.chunk("body"),
        ]
        result = _merge_chunk_content(chunks)
        self.assertEqual([c["content"] for c in result], ["cover", "# A\nbody"])


class ChunkSplitTests(unittest.TestCase):
    def test_long_text_without_punctuation_has_hard_limit_and_no_body_loss(self):
        body = "正文" * 1800
        chunk = ChunkMergeTests.chunk(body)
        original = copy.deepcopy(chunk)

        result = refine_split_and_merge_chunks([chunk])

        self.assertGreater(len(result), 1)
        self.assertTrue(all(400 <= len(c["content"]) <= 1000 for c in result))
        self.assertTrue(all(c["content"].startswith("# A\n") for c in result))
        self.assertEqual("".join(c["content"].removeprefix("# A\n") for c in result), body)
        self.assertEqual(chunk, original)

    def test_long_untitled_cover_preserves_text(self):
        content = "封面" * 1250
        chunk = {"title": None, "file_title": "manual", "content": content}

        result = refine_split_and_merge_chunks([chunk])

        self.assertTrue(all(len(c["content"]) <= 1000 for c in result))
        self.assertEqual("".join(c["content"] for c in result), content)

    def test_exactly_1000_characters_is_not_split(self):
        chunk = ChunkMergeTests.chunk("A" * 996)

        result = refine_split_and_merge_chunks([chunk])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["content"], chunk["content"])

    def test_long_table_splits_at_row_boundaries_and_preserves_all_rows(self):
        rows = [f"<tr><td>部件{i}</td><td>{'说明' * 30}</td></tr>" for i in range(17)]
        table = "<table>" + "".join(rows) + "</table>"

        result = refine_split_and_merge_chunks([ChunkMergeTests.chunk(table)])

        self.assertGreater(len(result), 1)
        self.assertTrue(all(400 <= len(c["content"]) <= 1000 for c in result))
        actual_rows = []
        for chunk in result:
            content = chunk["content"]
            tables = re.findall(r"<table>.*?</table>", content, re.S)
            self.assertEqual(len(tables), 1)
            self.assertEqual(content.count("<table>"), content.count("</table>"))
            actual_rows.extend(re.findall(r"<tr>.*?</tr>", tables[0], re.S))
        self.assertEqual(actual_rows, rows)

    def test_oversized_single_table_row_keeps_cell_text_and_length_limit(self):
        cell = "单元格内容" * 350
        table = "<table><tr><td>部件</td><td>" + cell + "</td></tr></table>"

        result = refine_split_and_merge_chunks([ChunkMergeTests.chunk(table)])

        self.assertTrue(all(len(c["content"]) <= 1000 for c in result))
        body = "".join(c["content"].removeprefix("# A\n") for c in result)
        self.assertEqual(re.sub(r"\s+", "", body), "部件" + cell)

    def test_sections_and_code_fence_headings_are_retained(self):
        md = "cover\n# A\nfirst\n```python\n# not a heading\n```\n# B\nsecond"

        result = split_document_by_title(md, "manual")

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["content"], "cover")
        self.assertIn("```python\n# not a heading\n```", result[1]["content"])
        self.assertEqual(result[2]["content"], "# B\nsecond")

    def test_real_manual_lengths_content_and_json_backup(self):
        source = Path(__file__).resolve().parents[1] / "output/hak180产品安全手册/hak180产品安全手册.md"
        md = source.read_text(encoding="utf-8")
        coarse = split_document_by_title(md, source.stem)
        original_rows = re.findall(r"<tr>.*?</tr>", md, re.S)

        with tempfile.TemporaryDirectory() as temporary_directory:
            md_path = Path(temporary_directory) / source.name
            md_path.write_text(md, encoding="utf-8")
            result = split_document({"md_path": str(md_path), "file_title": source.stem})
            chunks = result["chunks"]
            saved = json.loads(md_path.with_suffix(".json").read_text(encoding="utf-8"))

        self.assertEqual(len(coarse), 14)
        self.assertEqual(chunks, saved)
        self.assertTrue(all(0 < len(c["content"]) <= 1000 for c in chunks))
        for chunk in chunks:
            self.assertIn("parent_title", chunk)
            self.assertIn("part", chunk)
            self.assertNotIn("_source_section_index", chunk)
            self.assertEqual(chunk["content"].count("<table>"), chunk["content"].count("</table>"))
        actual_rows = [row for c in chunks for row in re.findall(r"<tr>.*?</tr>", c["content"], re.S)]
        self.assertEqual(actual_rows, original_rows)
        # 排除可重复的标题和表格外壳后，正文顺序与内容须和原文一致。
        def body_only(content):
            content = re.sub(r"^#{1,6}\s.*$", "", content, flags=re.M)
            content = re.sub(r"</?table\b[^>]*>", "", content)
            return re.sub(r"\s+", "", content)

        self.assertEqual("".join(body_only(c["content"]) for c in chunks), body_only(md))


if __name__ == "__main__":
    unittest.main()
