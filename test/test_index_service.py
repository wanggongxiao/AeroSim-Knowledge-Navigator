"""验证旧集合容量升级，以及不兼容集合在删除旧数据前停止。"""

import unittest
from unittest.mock import Mock, patch

from pymilvus import DataType

from app.rag.import_ import index_service


class IndexServiceTests(unittest.TestCase):
    def test_existing_small_content_field_is_expanded_once(self):
        client = Mock()
        client.has_collection.return_value = True
        client.describe_collection.side_effect = [
            {"fields": [{"name": "content", "type": DataType.VARCHAR, "params": {"max_length": 512}}]},
            {"fields": [{"name": "content", "type": DataType.VARCHAR, "params": {"max_length": 65535}}]},
        ]
        with patch.object(index_service.milvus_gateway, "client", return_value=client):
            index_service.prepare_chunks_collection()
            index_service.prepare_chunks_collection()
        client.alter_collection_field.assert_called_once_with(
            collection_name=index_service.milvus_gateway.chunks_collection,
            field_name="content",
            field_params={"max_length": 65535},
        )
        client.create_collection.assert_not_called()
        client.drop_collection.assert_not_called()

    def test_incompatible_collection_fails_before_deleting_old_data(self):
        client = Mock()
        client.has_collection.return_value = True
        client.describe_collection.return_value = {"fields": [{"name": "content", "type": DataType.INT64}]}
        with patch.object(index_service.milvus_gateway, "client", return_value=client):
            with self.assertRaisesRegex(ValueError, "VARCHAR"):
                index_service.index_chunks({"item_name": "Existing document", "chunks": [{"content": "Text"}]})
        client.delete.assert_not_called()
        client.insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
