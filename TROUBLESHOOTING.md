# 故障排除指南

## numpy/pandas兼容性问题

### 问题描述
```
ValueError: numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88 from PyObject
```

### 问题原因
这是一个典型的numpy和pandas版本不兼容问题，通常由以下原因导致：
1. pandas是用旧版本的numpy编译的，但运行时使用了新版本的numpy
2. 安装了不兼容的numpy/pandas版本组合

### 解决方案

#### 方案1：重新安装兼容版本（推荐）
```bash
# 1. 卸载现有的numpy和pandas
pip uninstall numpy pandas -y

# 2. 重新安装requirements.txt中的依赖
pip install -r requirements.txt
```

#### 方案2：强制重新安装
```bash
# 强制重新安装numpy和pandas
pip install --force-reinstall --no-cache-dir numpy pandas
```

#### 方案3：使用conda（如果使用conda环境）
```bash
conda install numpy pandas -c conda-forge
```

### 预防措施
1. 始终使用虚拟环境
2. 使用requirements.txt锁定版本
3. 定期更新依赖到兼容版本

## pyyaml导入问题

### 问题描述
环境检查显示pyyaml未安装，但实际已安装

### 原因
包名不匹配：安装名是`pyyaml`，但导入名是`yaml`

### 解决方案
已在app.py中修正检查逻辑，现在会正确检查yaml包的导入。

## 其他常见问题

### 虚拟环境问题
```bash
# 重新创建虚拟环境
rm -rf venv  # Linux/macOS
rmdir /s venv  # Windows
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 权限问题
```bash
# 使用用户安装
pip install --user -r requirements.txt
```