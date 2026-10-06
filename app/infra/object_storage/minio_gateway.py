"""
MinIO 门面模块，统一封装对象存储客户端与桶配置访问。
"""
from minio import Minio
from urllib.parse import quote

from app.shared.tool.clients.minio_utils import get_minio_client
from app.infra.config import infra_config


class MinIOGateway:
    @property
    def bucket_name(self) -> str:
        return infra_config.minio.bucket_name

    @property
    def image_dir(self) -> str:
        return infra_config.minio.minio_img_dir

    def client(self) -> Minio:
        return get_minio_client()

    def build_image_url(self, stem: str, image_name: str) -> str:
        """
        构建图片对象的公开访问地址。

        Args:
            stem: 当前文档或任务的目录名。
            image_name: 图片文件名。

        Returns:
            str: 对应图片在 MinIO 中的访问 URL。
        """
        endpoint = infra_config.minio.public_endpoint or infra_config.minio.endpoint
        protocol = "https" if infra_config.minio.minio_secure else "http"
        image_dir = infra_config.minio.minio_img_dir.strip("/")
        object_parts = [self.bucket_name, image_dir, stem.strip("/"), image_name.lstrip("/")]
        object_path = "/".join(quote(part, safe="") for part in object_parts if part)
        return (
            f"{protocol}://{endpoint}/{object_path}"
        )


minio_gateway = MinIOGateway()
