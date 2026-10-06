这是因为你当前运行在 **Docker/AutoDL 容器**中，而不是完整的 Linux 虚拟机。

容器里的 PID 1 不是 `systemd`，所以：

```bash
systemctl start minio
```

无法工作，才会出现：

```text
System has not been booted with systemd as init system
```

可以直接启动 MinIO 进程：

```bash
mkdir -p /root/minio-data

export MINIO_ROOT_USER=admin
export MINIO_ROOT_PASSWORD='设置一个强密码'

nohup minio server /root/minio-data \
  --address ":9000" \
  --console-address ":9001" \
  > /root/minio.log 2>&1 &
```

查看是否启动：

```bash
ps -ef | grep minio
tail -f /root/minio.log
```

访问地址：

```text
API：服务器IP:9000
控制台：服务器IP:9001
```

如果只想前台运行，直接执行：

```bash
minio server /root/minio-data --console-address ":9001"
```

但关闭终端后进程可能会停止。容器环境中通常使用：

- `nohup`
- `tmux`
- `supervisord`
- Docker Compose

来管理 MinIO，而不是使用 `systemctl`。







这条命令是在建立 **SSH 隧道**，把服务器里的 MinIO 控制台转发到你本地电脑。

```bash
ssh -L 9001:127.0.0.1:9001 root@服务器地址 -p SSH端口
```

拆开看：

```text
ssh
```

通过 SSH 连接服务器。

```text
-L 9001:127.0.0.1:9001
```

端口转发，含义是：

```text
本地电脑的 9001 端口
        ↓
SSH 隧道
        ↓
服务器内部的 127.0.0.1:9001
```

```text
root@服务器地址
```

使用 `root` 用户连接服务器。

```text
-p SSH端口
```

指定 SSH 端口。注意这里的 SSH 端口不一定是 MinIO 的 `9000` 或 `9001`，要使用 AutoDL 提供的 SSH 端口。

例如 AutoDL 给你的连接信息是：

```text
ssh root@connect.example.com -p 12345
```

那么应该改成：

```bash
ssh -L 9001:127.0.0.1:9001 root@connect.example.com -p 12345
```

连接成功后，不要关闭这个终端，然后在本地浏览器打开：

```text
http://127.0.0.1:9001
```

浏览器访问的是你本地的 `9001` 端口，但实际页面来自远程服务器中的 MinIO 控制台。

注意：

- 运行 SSH 命令的终端不能关闭；
- 关闭终端，隧道就会断开；
- `9001` 是 MinIO 控制台端口；
- `-p` 后面填写的是 SSH 登录端口，不是 MinIO 端口。