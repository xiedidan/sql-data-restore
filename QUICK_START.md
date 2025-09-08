# Oracle到多数据库迁移工具 - 快速启动指南

本工具现已支持向**Apache Doris**和**PostgreSQL**两种数据库迁移数据。

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装Python依赖
pip install -r requirements.txt

# 复制配置文件
cp config.yaml.example config.yaml
```

### 2. 配置数据库

编辑 `config.yaml` 文件：

```yaml
database:
  # 选择目标数据库类型
  target_type: "postgresql"  # 或 "doris"
  
  # PostgreSQL配置
  postgresql:
    host: "localhost"
    port: 5432
    user: "postgres"
    password: "your_password"
    database: "migration_db"
  
  # Doris配置
  doris:
    host: "localhost"
    port: 9030
    user: "root"
    password: ""
    database: "migration_db"
```

### 3. 启动Web界面

```bash
# Windows
start.bat

# Linux/Mac
./start.sh
```

访问: http://localhost:5000

## 🎯 主要功能

### 数据库类型选择
- **Apache Doris**: 高性能分析型数据库
- **PostgreSQL**: 功能强大的关系型数据库

### 输入方式
- **文件上传**: 直接上传SQL文件
- **服务器路径**: 指定服务器上的SQL文件路径

### 自动化处理
1. **SQL解析**: 自动解析Oracle SQL文件
2. **表结构推断**: AI推断目标数据库表结构
3. **语法转换**: 自动转换SQL语法
4. **并行导入**: 高性能并行数据导入

## 📊 Web界面使用

### 1. 选择目标数据库
在左侧面板选择目标数据库类型：
- 🔘 Apache Doris
- 🔘 PostgreSQL

### 2. 输入SQL文件
选择输入方式：
- **文件上传**: 拖拽或选择SQL文件
- **服务器路径**: 输入服务器文件路径

### 3. 确认表结构
系统会自动推断表结构，您可以：
- 直接确认使用推断的DDL
- 手动修改DDL语句
- 查看置信度评分

### 4. 监控导入进度
实时查看：
- 导入进度百分比
- 处理行数统计
- 错误信息提示

## 🔧 命令行使用

```python
from main_controller import OracleToDbMigrator

# 初始化迁移器
migrator = OracleToDbMigrator("config.yaml")

# 迁移单个表
success = migrator.migrate_single_table("data.sql")

# 批量迁移
success = migrator.migrate_multiple_tables(["table1.sql", "table2.sql"])
```

## 🛠️ 高级配置

### 性能优化
```yaml
migration:
  max_workers: 8              # 并发线程数
  batch_size: 1000           # 批处理大小
  enable_parallel_insert: true # 启用并行插入
  connection_pool_size: 8     # 连接池大小
```

### 通信模式
```yaml
web_interface:
  communication:
    mode: "auto"              # auto, websocket, polling, polling_only
    polling_interval: 2       # 轮询间隔（秒）
    websocket_timeout: 120    # WebSocket超时
```

## 🔍 SQL语法转换

系统会自动处理以下转换：

### Oracle → PostgreSQL
- `NUMBER(p,s)` → `NUMERIC(p,s)`
- `VARCHAR2(n)` → `VARCHAR(n)`
- `CLOB` → `TEXT`
- `DATE` → `DATE`
- `TIMESTAMP` → `TIMESTAMP`

### MySQL/Doris → PostgreSQL
- `TINYINT` → `SMALLINT`
- `DOUBLE` → `DOUBLE PRECISION`
- `DATETIME` → `TIMESTAMP`
- `LONGTEXT` → `TEXT`

### 数据库名称清理
- 自动移除 `EMR_HIS.table_name` 中的数据库前缀
- 清理 `[database].table` 格式的引用

## 📋 测试验证

```bash
# 运行系统测试
python test_system.py

# 运行数据库选择测试
python test_database_selection.py
```

## 🚨 故障排除

### 常见问题

1. **PostgreSQL连接失败**
   ```
   解决方案：
   - 检查PostgreSQL服务状态
   - 验证连接参数
   - 确认用户权限
   ```

2. **Doris连接失败**
   ```
   解决方案：
   - 检查Doris FE节点状态
   - 验证端口9030是否开放
   - 确认用户名密码
   ```

3. **文件编码问题**
   ```
   解决方案：
   - 检查SQL文件编码格式
   - 配置fallback_encodings
   - 使用UTF-8编码
   ```

### 日志查看
- Web应用日志: `web_app.log`
- 迁移日志: `migration.log`
- 控制台输出: 实时显示

## 🔄 数据库切换

### 运行时切换
通过Web界面API切换数据库类型：
```bash
curl -X POST http://localhost:5000/api/database/switch \
  -H "Content-Type: application/json" \
  -d '{"target_type": "postgresql"}'
```

### 配置文件切换
修改 `config.yaml` 中的 `target_type` 字段并重启应用。

## 📈 性能建议

### 硬件配置
- **CPU**: 多核处理器，推荐8核以上
- **内存**: 8GB以上，大文件处理建议16GB+
- **存储**: SSD硬盘，提升I/O性能

### 配置优化
- `max_workers`: 设置为CPU核心数的2倍
- `batch_size`: 根据内存大小调整（1000-5000）
- `connection_pool_size`: 等于max_workers
- `enable_parallel_insert`: 启用以获得最佳性能

## 🆘 获取帮助

- 查看详细文档: `README.md`
- PostgreSQL支持: `POSTGRESQL_SUPPORT.md`
- 故障排除: `TROUBLESHOOTING.md`
- 性能优化: `PERFORMANCE_OPTIMIZATION_REPORT.md`

---

🎉 **恭喜！** 您现在可以开始使用Oracle到多数据库迁移工具了！