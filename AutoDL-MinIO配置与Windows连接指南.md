# AutoDL MinIO 配置与 Windows 连接指南

本文说明如何在 AutoDL 容器中启动 MinIO，并从 Windows 访问 MinIO API 和控制台。

## 一、端口说明

| 端口 | 用途 | 是否给 Python 应用使用 |
| --- | --- | --- |
| `9000` | MinIO API、SDK、文件上传下载 | 是 |
| `9001` | MinIO Web 控制台 | 否 |
| `52031` | AutoDL SSH 登录端口示例 | 否 |

`9000` 和 `9001` 是容器内的 MinIO 端口，`52031` 是 AutoDL 提供的 SSH 端口。三者用途不同。

## 二、在 AutoDL 中启动 MinIO

AutoDL 通常是 Docker 容器，没有 `systemd`，因此不要使用：

```bash
systemctl start minio
```

直接启动 MinIO 进程：

```bash
mkdir -p /root/minio-data

export MINIO_ROOT_USER=admin
export MINIO_ROOT_PASSWORD='替换成强密码'

nohup minio server /root/minio-data \
  --address ":9000" \
  --console-address ":9001" \
  >/root/minio.log 2>&1 &
```

建议把账号密码和启动命令放在同一个终端执行，确保 MinIO 进程继承到正确的环境变量。

### 检查进程

```bash
ps -ef | grep '[m]inio'
```

查看日志：

```bash
tail -n 50 /root/minio.log
```

### 检查 API 健康状态

```bash
curl -i http://127.0.0.1:9000/minio/health/live
```

成功时应看到：

```text
HTTP/1.1 200 OK
```

如果直接使用下面的命令：

```bash
curl http://127.0.0.1:9000/minio/health/live
```

没有显示正文也可能是正常的，因为这个接口成功时可能返回空响应体。应以 `HTTP 200` 为准。

### 检查端口

```bash
ss -lntp | grep -E ':9000|:9001'
```

## 三、项目 `.env` 配置

应用和 MinIO 位于同一个 AutoDL 容器时，项目根目录的 `.env` 可以写成：

```env
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_PUBLIC_ENDPOINT=

MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=替换成强密码

MINIO_BUCKET_NAME=enterprise-rag
MINIO_IMG_DIR=kb-images
MINIO_SECURE=False
```

### 配置项说明

| 配置项 | 说明 |
| --- | --- |
| `MINIO_ENDPOINT` | Python SDK 连接地址，不要带 `http://` 或 `https://` |
| `MINIO_PUBLIC_ENDPOINT` | 浏览器访问图片时使用的地址，可以先留空 |
| `MINIO_ACCESS_KEY` | MinIO 用户名，应与 `MINIO_ROOT_USER` 一致 |
| `MINIO_SECRET_KEY` | MinIO 密码，应与 `MINIO_ROOT_PASSWORD` 一致 |
| `MINIO_BUCKET_NAME` | 存放图片的桶名称 |
| `MINIO_IMG_DIR` | 图片对象的目录前缀 |
| `MINIO_SECURE` | HTTP 使用 `False`，HTTPS 使用 `True` |

`MINIO_ENDPOINT` 的正确写法：

```env
MINIO_ENDPOINT=127.0.0.1:9000
```

不要写成：

```env
MINIO_ENDPOINT=http://127.0.0.1:9000
```

修改 `.env` 后需要重启 Python 程序，因为项目会在导入配置时读取环境变量。

## 四、Windows 访问 AutoDL 上的 MinIO

如果项目也运行在 AutoDL 容器中，可以直接使用：

```env
MINIO_ENDPOINT=127.0.0.1:9000
```

如果项目运行在 Windows，而 MinIO 运行在 AutoDL，Windows 中的 `127.0.0.1` 指向的是 Windows 本机，不是 AutoDL。因此需要通过 SSH 隧道转发 MinIO 的 API 端口 `9000`。

### 4.1 转发 MinIO API 端口

假设 AutoDL SSH 连接命令是：

```bash
ssh -p 52031 root@region-41.seetacloud.com
```

在 Windows PowerShell 中执行：

```powershell
ssh -N -o ExitOnForwardFailure=yes `
  -L 19000:127.0.0.1:9000 `
  -p 52031 `
  root@region-41.seetacloud.com
```

这个隧道表示：

```text
Windows 127.0.0.1:19000
        -> SSH 隧道
AutoDL 127.0.0.1:9000
        -> MinIO API
```

Windows 项目的 `.env` 应改为：

```env
MINIO_ENDPOINT=127.0.0.1:19000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=替换成强密码
MINIO_BUCKET_NAME=enterprise-rag
MINIO_IMG_DIR=kb-images
MINIO_SECURE=False
```

验证 API：

```powershell
curl.exe -i http://127.0.0.1:19000/minio/health/live
```

成功时应看到：

```text
HTTP/1.1 200 OK
```

然后运行项目测试：

```powershell
uv run python test/test_minio_connection.py
```

### 4.2 转发 MinIO 控制台端口

如果还需要在 Windows 浏览器打开 MinIO 控制台，可以同时转发 `9001`：

```powershell
ssh -N -o ExitOnForwardFailure=yes `
  -L 19000:127.0.0.1:9000 `
  -L 19001:127.0.0.1:9001 `
  -p 52031 `
  root@region-41.seetacloud.com
```

访问：

```text
API：http://127.0.0.1:19000
控制台：http://127.0.0.1:19001
```

项目的 `MINIO_ENDPOINT` 必须使用 API 端口 `19000`，不能使用控制台端口 `19001`。

### 4.3 端口被占用时

如果 Windows 本地 `19000` 或 `19001` 已被占用，可以换成本地其他端口，例如：

```powershell
ssh -N -L 29000:127.0.0.1:9000 -L 29001:127.0.0.1:9001 -p 52031 root@region-41.seetacloud.com
```

对应配置：

```env
MINIO_ENDPOINT=127.0.0.1:29000
```

控制台地址：

```text
http://127.0.0.1:29001
```

### 4.4 不要把 SSH 端口当作 MinIO 端口

下面的配置是错误的：

```env
MINIO_ENDPOINT=region-41.seetacloud.com:52031
```

`52031` 是 SSH 端口，不是 MinIO API 端口。项目需要通过端口转发访问 `9000`，或者使用 AutoDL 映射出来的 MinIO API 公网端口。

## 五、让 Windows 浏览器访问图片

SSH 隧道只用于访问控制台。如果 Markdown 图片也需要在 Windows 浏览器中打开，还需要为 MinIO API 配置一个 AutoDL 对外可访问的地址，并填入：

```env
MINIO_PUBLIC_ENDPOINT=AutoDL对外地址:映射端口
```

例如：

```env
MINIO_PUBLIC_ENDPOINT=region-41.seetacloud.com:映射出来的API端口
```

这里同样不要写协议：

```env
MINIO_PUBLIC_ENDPOINT=region-41.seetacloud.com:12345
```

如果没有对外暴露 API 端口，可以先保持为空：

```env
MINIO_PUBLIC_ENDPOINT=
```

## 六、在项目中验证连接

在项目目录执行：

```bash
uv run python -c "from app.infra.object_storage.minio_gateway import minio_gateway; client = minio_gateway.client(); print(client.bucket_exists(minio_gateway.bucket_name))"
```

成功时应输出：

```text
True
```

项目第一次调用客户端时会检查桶是否存在，不存在时自动创建。当前项目在创建新桶时会设置公开读取策略，以便 Markdown 图片通过 URL 访问。

## 七、登录提示 Access Key 不存在

如果控制台显示：

```text
The Access Key you provided does not exist in our records.
```

说明输入的用户名不是当前 MinIO 进程使用的 `MINIO_ROOT_USER`。可以重新用明确的账号密码启动：

```bash
pkill -f "minio server"

export MINIO_ROOT_USER=admin
export MINIO_ROOT_PASSWORD='替换成强密码'

nohup minio server /root/minio-data \
  --address ":9000" \
  --console-address ":9001" \
  >/root/minio.log 2>&1 &
```

然后重新建立 SSH 隧道并登录。

如果修改过账号密码，项目 `.env` 也必须同步修改：

```env
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=替换成强密码
```

如果密码曾经在聊天、截图或日志中暴露，应立即更换。

## 八、Windows 出现 WinError 10061

如果测试脚本报错：

```text
HTTPConnectionPool(host='127.0.0.1', port=9000)
WinError 10061
```

说明 Windows 正在连接本机的 `9000` 端口，但本机没有 MinIO 服务。请确认：

1. AutoDL 上的 MinIO 进程仍在运行。
2. Windows SSH 隧道转发的是 `9000` API 端口。
3. Windows `.env` 使用的是 `MINIO_ENDPOINT=127.0.0.1:19000`。
4. 建立隧道的 PowerShell 窗口没有关闭。

可以执行：

```powershell
curl.exe -i http://127.0.0.1:19000/minio/health/live
```

如果没有 `HTTP/1.1 200 OK`，先检查 SSH 隧道和 AutoDL 上的 MinIO 日志。

## 九、安全注意事项

- 不要把真实 MinIO 密码提交到 Git。
- 不要把 `.env` 提交到 Git。
- SSH 隧道关闭后，`127.0.0.1:9001` 将无法访问，这是正常现象。
- `9001` 是控制台端口，项目 SDK 应连接 `9000`。
- 生产环境不建议直接公开 MinIO 管理端口。
