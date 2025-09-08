# 快速修复指南

## 当前问题解决方案

如果您遇到以下问题，请按照对应的解决方案操作：

### 1. 脚本语法错误：`[[: not found`

**问题**: 使用 `sh start-venv.sh` 时出现语法错误

**解决方案**:
```bash
# 使用bash运行脚本（推荐）
bash start-venv.sh

# 或者使用POSIX兼容版本
sh start-venv-posix.sh
```

### 2. Python语法错误：`unexpected indent (app.py, line 941)`

**问题**: Web应用启动时出现缩进错误

**解决方案**: 已修复，请重新启动应用
```bash
python run_web.py
```

### 3. 虚拟环境检测问题

**问题**: 脚本无法正确检测虚拟环境

**解决方案**:
```bash
# 确认虚拟环境已激活
echo $VIRTUAL_ENV

# 如果未激活，请激活
source venv/bin/activate

# 然后使用Python直接启动
python run_web.py
```

## 推荐的启动流程

### 最简单的方法（推荐）

```bash
# 1. 确保在虚拟环境中
source venv/bin/activate

# 2. 直接启动Web界面
python run_web.py
```

### 使用脚本启动

```bash
# 1. 确保在虚拟环境中
source venv/bin/activate

# 2. 使用bash运行脚本
bash start-venv.sh
```

### 使用诊断工具

```bash
# 运行环境诊断
python diagnose.py

# 查看详细的环境信息和解决建议
```

## 常见问题快速检查

### 检查虚拟环境
```bash
echo $VIRTUAL_ENV
# 应该显示: /path/to/your/project/venv
```

### 检查Python路径
```bash
which python
# 应该指向: /path/to/your/project/venv/bin/python
```

### 检查依赖
```bash
python -c "import flask, flask_socketio, yaml; print('依赖OK')"
```

### 检查配置文件
```bash
ls -la config.yaml
# 应该存在且不为空
```

## 如果问题仍然存在

1. **重新创建虚拟环境**:
   ```bash
   deactivate
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **使用最简单的启动方式**:
   ```bash
   python run_web.py
   ```

3. **查看详细错误信息**:
   ```bash
   python diagnose.py
   ```

4. **检查日志文件**:
   ```bash
   tail -f web_app.log
   tail -f migration.log
   ```

## 联系支持

如果以上方法都无法解决问题，请提供：
- 操作系统信息
- Python版本 (`python --version`)
- 虚拟环境路径 (`echo $VIRTUAL_ENV`)
- 完整的错误信息

---

**更新时间**: 2025-01-XX  
**状态**: 问题已修复，建议使用 `python run_web.py` 启动