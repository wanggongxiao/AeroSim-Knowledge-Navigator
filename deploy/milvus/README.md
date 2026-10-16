# 本机 Milvus 恢复配置

原来的 Milvus 2.6.7 容器使用内置 etcd，启动时在 etcd 完成选举前读取元数据，触发 `panic: etcdserver: leader changed`。此配置将 etcd 3.5.23 独立运行，Compose 等待 etcd 健康后再启动同版本 Milvus。

从项目根目录启动：

```powershell
docker compose -f deploy/milvus/compose.yaml up -d --wait --wait-timeout 120
docker compose -f deploy/milvus/compose.yaml ps
uv run python -c "from pymilvus import MilvusClient; print(MilvusClient(uri='http://127.0.0.1:19530').list_collections())"
```

项目 `.env` 保持 `MILVUS_URL=http://127.0.0.1:19530`。Milvus API 使用 19530，健康检查使用 9091，etcd 仅在 Docker 网络中访问。需要覆盖 Milvus 参数时编辑此目录的 `user.yaml`。

日常停止和重新启动：

```powershell
docker compose -f deploy/milvus/compose.yaml stop
docker compose -f deploy/milvus/compose.yaml up -d --wait --wait-timeout 120
```

恢复时保留的资源：

- 使用中的原数据卷：`milvus_data`。
- 修复前的完整备份卷：`aerosim_milvus_backup_20261012`，已逐文件验证 SHA-256。
- 修复前的原容器：`milvus-standalone-before-repair-20261012`，保持停止。

原容器和新服务共享数据卷，必须保持原容器停止。备份卷是修复前的快照，不包含修复之后写入的数据。
