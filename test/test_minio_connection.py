"""Verify the configured MinIO endpoint and create a test bucket."""

from __future__ import annotations

import os
import sys

from app.shared.config.minio_config import minio_config
from app.shared.tool.clients.minio_utils import get_minio_client


def main() -> int:
    """Connect to MinIO and create the configured test bucket if needed."""
    test_bucket = os.getenv("MINIO_TEST_BUCKET", "aerosim-connection-test")

    if not minio_config.endpoint:
        print("MinIO 配置错误：MINIO_ENDPOINT 为空")
        return 1
    if not minio_config.access_key or not minio_config.secret_key:
        print("MinIO 配置错误：MINIO_ACCESS_KEY 或 MINIO_SECRET_KEY 为空")
        return 1
    if not minio_config.bucket_name:
        print("MinIO 配置错误：MINIO_BUCKET_NAME 为空")
        return 1

    print(f"连接地址：{minio_config.endpoint}")
    print(f"测试桶：{test_bucket}")

    try:
        # Reuse the project's client factory and its configured bucket setup.
        client = get_minio_client()
        if client is None:
            print("MinIO 连接失败：客户端没有成功创建")
            return 1

        if client.bucket_exists(test_bucket):
            print(f"测试桶已存在：{test_bucket}")
        else:
            client.make_bucket(test_bucket)
            print(f"测试桶创建成功：{test_bucket}")

        bucket_names = sorted(bucket.name for bucket in client.list_buckets())
        print(f"当前可访问的桶：{bucket_names}")
        print("MinIO 连接和创建桶测试通过")
        return 0
    except Exception as exc:
        print(f"MinIO 测试失败：{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
