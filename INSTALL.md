# 安装和部署指南

## 目录
- [系统要求](#系统要求)
- [安装步骤](#安装步骤)
- [配置说明](#配置说明)
- [部署方式](#部署方式)
- [故障排除](#故障排除)

## 系统要求

### 硬件要求
- **CPU**: 4核心以上（推荐8核心）
- **内存**: 8GB以上（推荐16GB+）
- **存储**: 100GB以上可用空间
- **网络**: 稳定的网络连接

### 软件要求
- **操作系统**: 
  - Windows 10+ / Windows Server 2016+
  - Linux (Ubuntu 18.04+, CentOS 7+)
  - macOS 10.15+
- **Python**: 3.8 - 3.11
- **数据库**: Apache Doris 1.2+

### 网络要求
- 能够访问DeepSeek API (`api.deepseek.com`)
- 能够连接到Doris数据库端口9030
- Web界面需要开放5000端口（可配置）

## 安装步骤

### 1. 环境准备

#### Windows环境
```bash
# 安装Python 3.8+
# 从 https://www.python.org/downloads/ 下载并安装

# 验证安装
python --version
pip --version
```

#### Linux环境
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv

# CentOS/RHEL
sudo yum install python3 python3-pip

# 验证安装
python3 --version
pip3 --version
```

#### macOS环境
```bash
# 使用Homebrew安装
brew install python@3.8

# 验证安装
python3 --version
pip3 --version
```

### 2. 下载项目

```bash
# 方式1：使用Git克隆
git clone <repository-url>
cd sql-data-restore

# 方式2：下载压缩包
# 从GitHub或其他源下载项目压缩包并解压
```

### 3. 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# 验证虚拟环境
which python  # Linux/macOS
where python  # Windows
```

### 4. 安装依赖

```bash
# 升级pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 验证关键依赖
python -c "import flask, pymysql, requests; print('依赖安装成功')"
```

### 5. 配置系统

```bash
# 复制配置文件
cp config.yaml.example config.yaml

# 编辑配置文件
# Windows: notepad config.yaml
# Linux/macOS: nano config.yaml 或 vim config.yaml
```

### 6. 环境检查

```bash
# 运行环境检查
python app.py --mode check

# 预期输出示例：
# ✅ Python版本符合要求
# ✅ 配置文件存在
# ✅ 所有依赖库已安装
# ✅ 示例数据: 2 个文件
```

## 配置说明

### 必需配置

#### 1. 数据库连接

```yaml
database:
  doris:
    host: "your-doris-host"      # 替换为实际Doris地址
    port: 9030                   # Doris FE查询端口
    user: "root"                 # 数据库用户名
    password: "your-password"    # 数据库密码
    database: "migration_db"     # 目标数据库名
```

**获取Doris连接信息**：
```sql
-- 在Doris中创建数据库
CREATE DATABASE IF NOT EXISTS migration_db;

-- 创建用户（可选）
CREATE USER 'migration_user'@'%' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON migration_db.* TO 'migration_user'@'%';
```

#### 2. DeepSeek API配置

```yaml
deepseek:
  api_key: "sk-your-api-key"    # 替换为实际API密钥
```

**获取DeepSeek API密钥**：
1. 访问 [DeepSeek官网](https://www.deepseek.com/)
2. 注册账号并登录
3. 进入API管理页面
4. 创建新的API密钥
5. 复制密钥到配置文件

### 可选配置

#### 性能调优

```yaml
migration:
  max_workers: 8          # 根据CPU核心数调整
  chunk_size_mb: 30       # 根据内存大小调整
  batch_size: 1000        # 根据网络延迟调整
```

**推荐配置**：
- **4核心8GB内存**: max_workers=4, chunk_size_mb=20
- **8核心16GB内存**: max_workers=8, chunk_size_mb=30
- **16核心32GB内存**: max_workers=16, chunk_size_mb=50

#### Web界面

```yaml
web_interface:
  host: "0.0.0.0"         # 监听所有网卡
  port: 5000              # Web服务端口
  secret_key: "random-secret-key"  # 随机密钥
```

## 部署方式

### 开发环境部署

适用于测试和开发环境：

```bash
# 激活虚拟环境
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 启动Web服务
python app.py --mode web

# 访问 http://localhost:5000
```

### 生产环境部署

#### 使用Gunicorn（推荐）

```bash
# 安装Gunicorn
pip install gunicorn

# 创建启动脚本
cat > start_web.py << 'EOF'
from web.app import MigrationWebApp

app = MigrationWebApp("config.yaml")
application = app.app

if __name__ == "__main__":
    application.run()
EOF

# 启动服务
gunicorn -w 4 -b 0.0.0.0:5000 start_web:application
```

#### 使用Systemd服务

```bash
# 创建服务文件
sudo tee /etc/systemd/system/migration-tool.service << 'EOF'
[Unit]
Description=Oracle to Doris Migration Tool
After=network.target

[Service]
Type=exec
User=your-user
Group=your-group
WorkingDirectory=/path/to/sql-data-restore
Environment=PATH=/path/to/sql-data-restore/venv/bin
ExecStart=/path/to/sql-data-restore/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 start_web:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable migration-tool
sudo systemctl start migration-tool
```

#### 使用Docker

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py", "--mode", "web"]
```

```bash
# 构建镜像
docker build -t migration-tool .

# 运行容器
docker run -d \
  --name migration-tool \
  -p 5000:5000 \
  -v $(pwd)/config.yaml:/app/config.yaml \
  migration-tool
```

#### 使用Nginx反向代理

```nginx
# /etc/nginx/sites-available/migration-tool
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket支持
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
# 启用站点
sudo ln -s /etc/nginx/sites-available/migration-tool /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 故障排除

### 常见安装问题

#### 1. Python版本不兼容

```bash
# 错误信息
python: command not found
# 或
SyntaxError: invalid syntax

# 解决方案
# 确保安装Python 3.8+
python3 --version
pip3 install -r requirements.txt
```

#### 2. 依赖安装失败

```bash
# 错误信息
ERROR: Could not build wheels for xxx

# 解决方案 - Windows
# 安装Visual Studio Build Tools
# 或使用预编译包
pip install --only-binary=all -r requirements.txt

# 解决方案 - Linux
sudo apt-get install python3-dev build-essential
# 或
sudo yum groupinstall "Development Tools"
```

#### 3. 权限问题

```bash
# 错误信息
PermissionError: [Errno 13] Permission denied

# 解决方案
# 使用虚拟环境或用户安装
pip install --user -r requirements.txt
```

### 运行时问题

#### 1. 端口被占用

```bash
# 错误信息
OSError: [Errno 98] Address already in use

# 解决方案
# 查找占用进程
sudo netstat -tlnp | grep :5000
# 杀死进程或使用其他端口
```

#### 2. 数据库连接失败

```bash
# 错误信息
pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")

# 解决方案
# 1. 检查Doris服务状态
# 2. 验证网络连通性
telnet doris-host 9030
# 3. 检查防火墙设置
# 4. 验证用户权限
```

#### 3. API调用失败

```bash
# 错误信息
requests.exceptions.ConnectionError

# 解决方案
# 1. 检查网络连接
ping api.deepseek.com
# 2. 验证API密钥
# 3. 检查代理设置
```

### 性能问题

#### 1. 内存不足

```bash
# 症状：进程被杀死或响应缓慢

# 解决方案
# 1. 减少并发数和块大小
migration:
  max_workers: 4
  chunk_size_mb: 10

# 2. 增加系统内存
# 3. 使用更小的批次大小
```

#### 2. 磁盘空间不足

```bash
# 症状：导入失败或临时文件创建失败

# 解决方案
# 1. 清理临时文件
rm -rf ./temp/*

# 2. 修改临时目录位置
migration:
  temp_dir: "/path/to/large/disk/temp"

# 3. 增加磁盘空间
```

### 日志分析

#### 启用详细日志

```yaml
logging:
  level: "DEBUG"
  file: "migration.log"
```

#### 常见日志信息

```bash
# 正常流程
INFO - SQL文件解析完成
INFO - 表结构推断成功
INFO - 表创建成功
INFO - 数据导入完成

# 错误信息
ERROR - 推断表结构失败
ERROR - 创建表失败
ERROR - 导入数据异常
```

### 获取支持

如果遇到无法解决的问题：

1. 查看项目文档和FAQ
2. 搜索已有的Issue
3. 创建新的Issue并提供：
   - 操作系统和Python版本
   - 完整的错误信息和日志
   - 配置文件（隐藏敏感信息）
   - 重现步骤

## 更新和维护

### 更新项目

```bash
# 备份配置
cp config.yaml config.yaml.bak

# 更新代码
git pull origin main

# 更新依赖
pip install -r requirements.txt --upgrade

# 恢复配置
cp config.yaml.bak config.yaml
```

### 定期维护

```bash
# 清理日志文件
find . -name "*.log" -mtime +30 -delete

# 清理临时文件
rm -rf ./temp/*

# 检查磁盘空间
df -h

# 监控进程状态
ps aux | grep python
```