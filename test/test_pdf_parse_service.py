"""PDF 解析结果到下游 Markdown 节点的离线回归测试。"""

import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from app.process.import_.agent.state import create_default_state
from app.rag.import_ import pdf_parse_service
from app.rag.import_.enrich_markdown_images import vaildate_and_data


class PDFParseServiceTests(unittest.TestCase):
    def zip_response(self, name, content):
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr(name, content)
        return Mock(status_code=200, content=buffer.getvalue())

    def test_fresh_result_reaches_markdown_node(self):
        content = "# 安全手册\n\n操作说明。"
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "安全手册.pdf"
            pdf.touch()
            output = root / "output"
            state = create_default_state(pdf_path=str(pdf), local_dir=str(output))
            with patch.object(pdf_parse_service, "update_pdf_and_poll", return_value="https://example.com/result.zip"), patch.object(
                pdf_parse_service.requests, "Session"
            ) as session_factory:
                session = session_factory.return_value.__enter__.return_value
                session.get.return_value = self.zip_response("full.md", content)
                result = pdf_parse_service.parse_pdf_to_markdown(state)

            expected_path = output / "安全手册" / "安全手册.md"
            self.assertEqual(result["md_path"], str(expected_path))
            self.assertTrue(expected_path.is_file())
            self.assertFalse((expected_path.parent / "full.md").exists())
            self.assertEqual(result["md_content"], content)
            self.assertEqual(result["local_dir"], str(output))
            _, images, downstream_content = vaildate_and_data(result)
            self.assertEqual(images, expected_path.parent / "images")
            self.assertEqual(downstream_content, content)

    def test_already_named_markdown(self):
        with TemporaryDirectory() as directory, patch.object(
            pdf_parse_service.requests, "Session"
        ) as session_factory:
            session_factory.return_value.__enter__.return_value.get.return_value = self.zip_response("manual.md", "# Manual")
            path = pdf_parse_service.download_and_extract_markdown("https://example.com/result.zip", Path(directory), "manual")
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_text(encoding="utf-8"), "# Manual")

    def test_unexpected_markdown_name_has_clear_error(self):
        with TemporaryDirectory() as directory, patch.object(
            pdf_parse_service.requests, "Session"
        ) as session_factory:
            session_factory.return_value.__enter__.return_value.get.return_value = self.zip_response("other.md", "# Other")
            with self.assertRaisesRegex(RuntimeError, "full.md"):
                pdf_parse_service.download_and_extract_markdown("https://example.com/result.zip", Path(directory), "manual")


if __name__ == "__main__":
    unittest.main()
