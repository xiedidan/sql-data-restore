# 虚拟环境使用指南

## 问题说明

如果您在已激活的虚拟环境中运行 `start.sh` 时遇到Python检测问题，这是因为启动脚本在检测Python时使用了系统路径而不是虚拟环境路径。

## 解决方案

### 方案1: 使用修复后的启动脚本

我们已经修复了 `start.sh` 脚本，现在它能正确检测虚拟环境：

```bash
# 在已激活的虚拟环境中运行
./start.sh
```

### 方案2: 使用虚拟环境专用启动脚本

```bash
# 方法1: 使用bash运行（推荐）
bash start-venv.sh

# 方法2: 给脚本添加执行权限后直接运行
chmod +x start-venv.sh
./start-venv.sh

# 方法3: 使用POSIX兼容版本（如果遇到语法问题）
chmod +x start-venv-posix.sh
./start-venv-posix.sh
# 或
sh start-venv-posix.sh
```

### 方案3: 使用Python直接启动

```bash
# 直接启动Web界面
python run_web.py

# 或者使用原始方式
python app.py --mode web
```

### 方案4: 手动启动步骤

```bash
# 1. 确认在虚拟环境中
echo $VIRTUAL_ENV

# 2. 安装依赖（如果需要）
pip install -r requirements.txt

# 3. 检查配置文件
ls -la config.yaml

# 4. 启动Web应用
python -c "from web.app import MigrationWebApp; app = MigrationWebApp('config.yaml'); app.run()"
```

## 虚拟环境检查

### 确认虚拟环境状态

```bash
# 检查是否在虚拟环境中
echo $VIRTUAL_ENV

# 检查Python路径
which python
which pip

# 检查Python版本
python --version
```

### 预期输出

```bash
# $VIRTUAL_ENV 应该显示虚拟环境路径
/sas_1/project/sql-data-restore/venv

# which python 应该指向虚拟环境
/sas_1/project/sql-data-restore/venv/bin/python

# Python版本应该是3.8+
Python 3.x.x
```

## 常见问题解决

### 1. 虚拟环境未激活

```bash
# 激活虚拟环境
source venv/bin/activate

# 确认激活成功
echo $VIRTUAL_ENV
```

### 2. 依赖库缺失

```bash
# 在虚拟环境中安装依赖
pip install -r requirements.txt

# 检查关键依赖
python -c "import flask, flask_socketio, yaml; print('依赖OK')"
```

### 3. 配置文件问题

```bash
# 检查配置文件
ls -la config.yaml

# 如果不存在，复制示例文件
cp config.yaml.example config.yaml

# 编辑配置文件
nano config.yaml  # 或使用其他编辑器
```

### 4. 端口占用问题

```bash
# 检查端口5000是否被占用
netstat -tlnp | grep :5000

# 或者使用其他端口启动
python app.py --mode web --port 5001
```

## 推荐的启动流程

```bash
# 1. 进入项目目录
cd /sas_1/project/sql-data-restore

# 2. 激活虚拟环境（如果未激活）
source venv/bin/activate

# 3. 确认环境
echo "虚拟环境: $VIRTUAL_ENV"
python --version

# 4. 安装/更新依赖
pip install -r requirements.txt

# 5. 检查配置
ls -la config.yaml

# 6. 启动应用（选择一种方式）
python run_web.py                    # 推荐：简化启动器
# 或
./start-venv.sh                      # 完整启动脚本
# 或
python app.py --mode web             # 直接启动
```

## 测试功能

在虚拟环境中，您还可以运行各种测试：

```bash
# 系统功能测试
python test_system.py

# 数据库选择功能测试
python test_database_selection.py

# 环境检查
python app.py --mode check
```

## 故障排除

如果仍然遇到问题，请：

1. **检查Python路径**:
   ```bash
   which python
   # 应该指向: /path/to/your/project/venv/bin/python
   ```

2. **检查虚拟环境变量**:
   ```bash
   echo $VIRTUAL_ENV
   # 应该显示虚拟环境路径
   ```

3. **重新创建虚拟环境**:
   ```bash
   deactivate
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **查看详细错误**:
   ```bash
   python run_web.py
   # 会显示详细的错误信息和解决建议
   ```

## 联系支持

如果问题仍然存在，请提供以下信息：

- 操作系统版本
- Python版本 (`python --version`)
- 虚拟环境路径 (`echo $VIRTUAL_ENV`)
- 错误信息的完整输出

这将帮助我们更好地诊断和解决问题。