# 项目重命名设计：将"xindu"替换为"sql"

## 概述

本设计文档规划将整个项目中的"xindu"字样全部替换为"sql"，包括目录名、文件名、文件内容等所有出现的地方。这是一个系统性的重命名操作，需要确保所有引用都能正确更新。

## 技术架构

### 当前项目结构
```
xindu-data-restore/
├── core/                    # 核心业务模块
│   ├── __init__.py
│   ├── sql_parser.py       # SQL文件解析
│   ├── schema_inference.py # AI推断引擎
│   ├── doris_connection.py # 数据库连接
│   └── parallel_importer.py # 并行导入
├── web/                     # Web界面模块
├── templates/               # HTML模板
├── static/                  # 静态资源
├── tests/                   # 测试相关
├── temp/                    # 临时文件目录
├── main_controller.py       # 主控制器
├── app.py                  # 快速启动入口
├── config.yaml.example     # 配置示例
├── requirements.txt        # Python依赖
├── README.md              # 主要文档
├── INSTALL.md             # 安装指南
└── PROJECT_SUMMARY.md     # 项目概述
```

### 目标项目结构
```
sql-data-restore/
├── core/                    # 核心业务模块
├── web/                     # Web界面模块
├── templates/               # HTML模板
├── static/                  # 静态资源
├── tests/                   # 测试相关
├── temp/                    # 临时文件目录
├── main_controller.py       # 主控制器
├── app.py                  # 快速启动入口
├── config.yaml.example     # 配置示例
├── requirements.txt        # Python依赖
├── README.md              # 主要文档
├── INSTALL.md             # 安装指南
└── PROJECT_SUMMARY.md     # 项目概述
```

## 重命名范围分析

### 1. 目录名重命名
- `xindu-data-restore` → `sql-data-restore`

### 2. 文件内容重命名
基于代码搜索结果，需要更新以下文件中的内容：

#### 2.1 文档文件
- `README.md`: 8处引用需要更新
  - Git克隆命令中的目录名
  - GitHub Issues和Discussions链接
- `INSTALL.md`: 4处引用需要更新
  - Git克隆后的cd命令
  - Systemd服务配置中的工作目录路径
- `PROJECT_SUMMARY.md`: 1处引用需要更新
  - 项目结构图中的根目录名

#### 2.2 配置和引用更新
所有文件中涉及到项目路径引用的地方都需要相应更新。

## 重命名实施方案

### 阶段1：文件内容更新

#### 更新INSTALL.md
```diff
- cd xindu-data-restore
+ cd sql-data-restore

- WorkingDirectory=/path/to/xindu-data-restore
+ WorkingDirectory=/path/to/sql-data-restore

- Environment=PATH=/path/to/xindu-data-restore/venv/bin
+ Environment=PATH=/path/to/sql-data-restore/venv/bin

- ExecStart=/path/to/xindu-data-restore/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 start_web:application
+ ExecStart=/path/to/sql-data-restore/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 start_web:application
```

#### 更新README.md
```diff
- cd xindu-data-restore
+ cd sql-data-restore

- [GitHub Issues](https://github.com/example/xindu-data-restore/issues)
+ [GitHub Issues](https://github.com/example/sql-data-restore/issues)

- [GitHub Discussions](https://github.com/example/xindu-data-restore/discussions)
+ [GitHub Discussions](https://github.com/example/sql-data-restore/discussions)
```

#### 更新PROJECT_SUMMARY.md
```diff
- xindu-data-restore/
+ sql-data-restore/
```

### 阶段2：目录重命名

最后一步是将整个项目目录从 `xindu-data-restore` 重命名为 `sql-data-restore`。

## 风险评估与注意事项

### 潜在风险
1. **Git历史丢失**: 重命名目录可能影响Git历史追踪
2. **外部引用失效**: 如果有外部脚本或工具引用了旧的目录名
3. **配置文件路径**: 绝对路径引用需要手动更新

### 缓解措施
1. **备份**: 在重命名前创建完整备份
2. **分步执行**: 先更新文件内容，后重命名目录
3. **验证测试**: 重命名后运行完整测试验证功能正常

### 验证清单
- [ ] 所有文档文件中的"xindu"引用已更新
- [ ] 配置文件中的路径引用已更新  
- [ ] 项目可以正常启动和运行
- [ ] 所有功能测试通过
- [ ] 文档描述准确反映新的项目名称

## 实施步骤

1. **文档内容更新**: 更新INSTALL.md、README.md、PROJECT_SUMMARY.md中的所有"xindu"引用
2. **功能验证**: 确保更新后项目功能正常
3. **目录重命名**: 将项目根目录重命名为新名称
4. **最终验证**: 确认所有更改生效且项目正常运行

## 兼容性考虑

### Git操作
重命名操作完成后，如果项目使用Git版本控制，建议：
1. 提交所有文件内容更改
2. 使用`git mv`命令重命名（如果在Git仓库内操作）
3. 更新`.gitignore`文件中可能包含的路径引用

### 部署脚本
如果存在自动化部署脚本，需要同步更新：
1. 构建脚本中的路径引用
2. 部署配置中的目录名
3. 监控和日志配置中的路径

## 测试策略

### 功能测试
1. **基本功能**: 验证文件上传、DDL推断、数据导入等核心功能
2. **Web界面**: 确认Web界面正常加载和交互
3. **配置加载**: 验证配置文件正确读取
4. **API调用**: 确认DeepSeek API调用正常

### 回归测试
运行现有的测试套件，确保重命名操作没有影响功能：
```bash
python app.py --mode test
pytest tests/
```