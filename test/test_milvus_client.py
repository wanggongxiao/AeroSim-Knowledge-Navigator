"""验证连接失败保留原始原因，且不会缓存失败的客户端。"""

import unittest
from unittest.mock import Mock, patch

from app.shared.tool.clients import milvus_utils


class MilvusClientTests(unittest.TestCase):
    def test_failure_preserves_cause_and_next_call_retries(self):
        cause = RuntimeError("server unavailable")
        client = Mock()
        with patch.object(milvus_utils, "_milvus_client", None), patch.object(
            milvus_utils.milvus_config, "milvus_url", "http://127.0.0.1:19530"
        ), patch.object(milvus_utils, "MilvusClient", side_effect=[cause, client]) as factory:
            with self.assertRaises(ConnectionError) as caught:
                milvus_utils.get_milvus_client()
            self.assertIs(caught.exception.__cause__, cause)
            self.assertIsNone(milvus_utils._milvus_client)
            self.assertIs(milvus_utils.get_milvus_client(), client)
            self.assertIs(milvus_utils.get_milvus_client(), client)
            self.assertEqual(factory.call_count, 2)

    def test_missing_config_stops_before_sdk_connection(self):
        with patch.object(milvus_utils, "_milvus_client", None), patch.object(
            milvus_utils.milvus_config, "milvus_url", ""
        ), patch.object(milvus_utils, "MilvusClient") as factory:
            with self.assertRaisesRegex(ConnectionError, "MILVUS_URL"):
                milvus_utils.get_milvus_client()
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
