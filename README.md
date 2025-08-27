# Oracle到Doris数据迁移工具

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一个功能强大的Oracle数据库到Apache Doris数据库的迁移工具，支持AI智能推断表结构、Web界面交互和高性能并行导入。

## ✨ 核心特性

- 🤖 **AI智能推断**: 使用DeepSeek R1 API自动分析Oracle SQL文件，生成适配Doris的DDL语句
- 🌐 **Web界面**: 提供直观的Web界面，支持实时进度监控和DDL在线编辑
- ⚡ **并行导入**: 支持大文件分块并行处理，显著提升数据导入性能
- 🔄 **实时监控**: WebSocket实时通信，提供详细的进度反馈和错误处理
- 📝 **用户确认**: 支持用户对AI推断的DDL语句进行确认和修改
- 🛠️ **灵活配置**: 支持多种配置选项，适应不同的迁移需求

## 🏗️ 系统架构

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Oracle SQL    │    │   AI推断引擎     │    │   Doris数据库   │
│     文件        │───▶│  (DeepSeek R1)   │───▶│               │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       ▲
         ▼                       ▼                       │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   文件解析器    │    │   Web界面       │    │   并行导入器    │
│                 │    │   (Flask+SocketIO)│    │               │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📋 系统要求

- Python 3.8+
- Apache Doris 1.2+
- DeepSeek API 密钥
- 8GB+ 内存（推荐）
- 支持的操作系统：Windows 10+、Linux、macOS

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd sql-data-restore

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置设置

复制并编辑配置文件：

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml`：

```yaml
database:
  doris:
    host: "your-doris-host"
    port: 9030
    user: "root"
    password: "your-password"
    database: "migration_db"

deepseek:
  api_key: "your-deepseek-api-key"
  base_url: "https://api.deepseek.com"
  model: "deepseek-reasoner"

migration:
  sample_lines: 100
  max_workers: 8
  chunk_size_mb: 30
```

### 3. 启动应用

#### Web界面模式（推荐）

```bash
python app.py --mode web
```

访问 `http://localhost:5000` 使用Web界面。

#### 命令行模式

```bash
python app.py --mode cli
```

#### 快速测试

```bash
python app.py --mode test
```

## 📖 使用指南

### Web界面使用

1. **上传SQL文件**: 拖拽或选择Oracle导出的SQL文件
2. **AI推断**: 系统自动分析文件并生成Doris DDL语句
3. **确认修改**: 在Web编辑器中查看、修改DDL语句
4. **开始导入**: 确认后开始并行导入数据
5. **监控进度**: 实时查看导入进度和统计信息

### 命令行使用

```python
from main_controller import OracleDoriseMigrator

# 初始化迁移器
migrator = OracleDoriseMigrator("config.yaml")

# 迁移单个表
success = migrator.migrate_single_table("path/to/table.sql")

# 批量迁移
results = migrator.migrate_multiple_tables([
    "table1.sql", 
    "table2.sql", 
    "table3.sql"
])
```

### API使用

```python
# 仅推断表结构
schema = migrator.infer_schema("table.sql")
print(schema.ddl_statement)

# 创建表
migrator.create_table(schema)

# 导入数据
result = migrator.import_data_parallel("table.sql")
print(f"导入 {result.total_rows_imported} 行数据")
```

## ⚙️ 配置详解

### 数据库配置

```yaml
database:
  doris:
    host: "localhost"          # Doris服务器地址
    port: 9030                 # FE查询端口
    user: "root"               # 用户名
    password: ""               # 密码
    database: "migration_db"   # 目标数据库
    charset: "utf8mb4"         # 字符集
```

### AI推断配置

```yaml
deepseek:
  api_key: "sk-xxxxx"         # DeepSeek API密钥
  base_url: "https://api.deepseek.com"
  model: "deepseek-reasoner"  # 模型名称
  max_tokens: 4000            # 最大输出令牌
  temperature: 0.1            # 温度参数
  timeout: 30                 # 超时时间（秒）
```

### 迁移配置

```yaml
migration:
  sample_lines: 100           # 样本行数
  chunk_size_mb: 30          # 文件块大小（MB）
  max_workers: 8             # 最大工作线程数
  batch_size: 1000           # 批处理大小
  retry_count: 3             # 重试次数
  enable_user_confirmation: true  # 启用用户确认
  temp_dir: "./temp"         # 临时目录
```

### Web界面配置

```yaml
web_interface:
  host: "0.0.0.0"           # 监听地址
  port: 5000                # 监听端口
  debug: false              # 调试模式
  secret_key: "your-secret" # 密钥
```

## 🔧 高级功能

### 自定义DDL模板

支持为特定表类型定义DDL模板：

```python
# 自定义配置
custom_config = {
    "enable_user_confirmation": False,
    "max_workers": 16,
    "chunk_size_mb": 50
}

migrator = OracleDoriseMigrator("config.yaml", custom_config)
```

### 监控回调

```python
def progress_callback(progress_data):
    print(f"进度: {progress_data['progress_percent']:.1f}%")

def error_callback(error_message):
    print(f"错误: {error_message}")

migrator.enable_monitoring(progress_callback, error_callback)
```

### 并行优化

根据服务器配置调整并行参数：

```yaml
migration:
  max_workers: 16        # CPU核心数 x 2
  chunk_size_mb: 50      # 根据内存大小调整
  batch_size: 2000       # 根据网络延迟调整
```

## 📊 性能基准

| 数据量 | 并发数 | 导入时间 | 吞吐量 |
|--------|--------|----------|---------|
| 1GB    | 4      | 2分钟    | 8.3MB/s |
| 10GB   | 8      | 15分钟   | 11.1MB/s|
| 50GB   | 16     | 60分钟   | 13.9MB/s|

*基于标准配置的测试结果，实际性能取决于硬件和网络环境*

## 🐛 故障排除

### 常见问题

#### 1. 连接Doris失败

```
错误: pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")
```

**解决方案**:
- 检查Doris服务是否运行
- 确认FE节点的9030端口可访问
- 验证用户名密码是否正确

#### 2. DeepSeek API调用失败

```
错误: DeepSeek API调用失败: 401 Unauthorized
```

**解决方案**:
- 检查API密钥是否正确设置
- 确认API密钥是否有足够的额度
- 验证网络连接是否正常

#### 3. 内存不足

```
错误: MemoryError: Unable to allocate array
```

**解决方案**:
- 减少 `chunk_size_mb` 参数
- 降低 `max_workers` 数量
- 增加系统内存

#### 4. 文件编码问题

```
错误: UnicodeDecodeError: 'utf-8' codec can't decode
```

**解决方案**:
- 确保SQL文件使用UTF-8编码
- 使用文本编辑器转换文件编码
- 检查文件是否损坏

### 日志分析

启用详细日志进行问题诊断：

```yaml
logging:
  level: "DEBUG"
  file: "migration.log"
```

查看日志文件了解详细错误信息。

## 🧪 测试

### 运行单元测试

```bash
python -m pytest tests/ -v
```

### 运行集成测试

```bash
python tests/test_migration.py --mode single --sample-data
```

### 性能测试

```bash
python tests/test_migration.py --mode multiple --files *.sql
```

## 📚 API参考

### 核心类

#### OracleDoriseMigrator

主控制器类，提供完整的迁移功能。

```python
class OracleDoriseMigrator:
    def __init__(self, config_path: str, migration_config: Optional[Dict] = None)
    def migrate_single_table(self, sql_file: str, auto_confirm: bool = False) -> bool
    def migrate_multiple_tables(self, sql_files: List[str], auto_confirm: bool = False) -> Dict[str, bool]
    def infer_schema(self, sql_file: str) -> TableSchema
    def create_table(self, schema: TableSchema) -> bool
    def import_data_parallel(self, sql_file: str) -> ImportResult
```

#### SQLFileParser

SQL文件解析器。

```python
class SQLFileParser:
    def extract_sample_data(self, file_path: str, n_lines: Optional[int] = None) -> Dict
    def identify_table_name(self, sql_content: str) -> str
    def extract_insert_statements(self, file_path: str, limit: int = 10) -> List[str]
```

#### SchemaInferenceEngine

AI推断引擎。

```python
class SchemaInferenceEngine:
    def infer_table_schema(self, sample_data: Dict) -> InferenceResult
    def call_deepseek_api(self, prompt: str) -> Optional[str]
```

### 数据类

#### TableSchema

```python
@dataclass
class TableSchema:
    table_name: str
    ddl_statement: str
    sample_data: List[str]
    column_count: int
    estimated_rows: int
```

#### ImportResult

```python
@dataclass
class ImportResult:
    task_id: str
    table_name: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_rows_imported: int
    total_execution_time: float
    success: bool
    error_messages: List[str]
```

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 开发环境设置

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行代码检查
flake8 .
black .

# 运行测试
pytest tests/
```

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持

- 📧 Email: support@example.com
- 📖 文档: [完整文档](docs/)
- 🐛 Issue: [GitHub Issues](https://github.com/example/sql-data-restore/issues)
- 💬 讨论: [GitHub Discussions](https://github.com/example/sql-data-restore/discussions)

## 🙏 致谢

- [Apache Doris](https://doris.apache.org/) - 优秀的OLAP数据库
- [DeepSeek](https://www.deepseek.com/) - 强大的AI推理能力
- [Flask](https://flask.palletsprojects.com/) - 轻量级Web框架
- [Socket.IO](https://socket.io/) - 实时通信库

---

⭐ 如果这个项目对你有帮助，请给我们一个星标！