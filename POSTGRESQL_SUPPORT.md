# PostgreSQL支持功能说明

本项目现已支持向PostgreSQL数据库写入数据，用户可以选择向Doris或PostgreSQL写入。

## 新增功能

### 1. 数据库类型选择
- 支持Apache Doris和PostgreSQL两种目标数据库
- 可在Web界面中选择目标数据库类型
- 支持运行时切换数据库类型

### 2. PostgreSQL连接模块
- 新增 `core/postgresql_connection.py` 模块
- 支持PostgreSQL连接池管理
- 自动进行SQL语法转换（MySQL/Oracle → PostgreSQL）
- 支持并行批量插入

### 3. 数据库工厂模式
- 新增 `core/database_factory.py` 工厂类
- 根据配置自动选择合适的数据库连接
- 统一的配置验证机制

## 配置说明

### 配置文件更新
在 `config.yaml` 中添加PostgreSQL配置：

```yaml
database:
  # 目标数据库类型选择: doris 或 postgresql
  target_type: "postgresql"  # 可选值: "doris", "postgresql"
  
  doris:
    host: "localhost"
    port: 9030
    user: "root"
    password: ""
    database: "migration_db"
    charset: "utf8mb4"
  
  postgresql:
    host: "localhost"
    port: 5432
    user: "postgres"
    password: ""
    database: "migration_db"
```

### 依赖包更新
新增PostgreSQL驱动依赖：
```
psycopg2-binary==2.9.7
```

## 使用方法

### 1. Web界面使用
1. 打开Web界面
2. 在"目标数据库"区域选择数据库类型（Doris或PostgreSQL）
3. 上传SQL文件或输入服务器路径
4. 系统将自动使用选择的数据库类型进行迁移

### 2. 命令行使用
```python
from main_controller import OracleToDbMigrator

# 配置文件中指定target_type
migrator = OracleToDbMigrator("config.yaml")
success = migrator.migrate_single_table("data.sql")
```

## 技术特性

### 1. SQL语法自动转换
PostgreSQL连接模块会自动转换SQL语法：

**数据类型映射：**
- `TINYINT` → `SMALLINT`
- `DOUBLE` → `DOUBLE PRECISION`
- `DATETIME` → `TIMESTAMP`
- `NUMBER(p,s)` → `NUMERIC(p,s)`
- `VARCHAR2(n)` → `VARCHAR(n)`
- `CLOB` → `TEXT`

**语法清理：**
- 移除MySQL/Doris特有的`ENGINE`、`CHARSET`等
- 移除`AUTO_INCREMENT`，使用`SERIAL`代替
- 处理日期格式转换

### 2. 连接池支持
- PostgreSQL连接池管理
- 并行批量插入优化
- 连接健康检查和自动重连

### 3. 错误处理
- 详细的错误信息和日志
- 配置验证和提示
- 连接失败自动重试

## API接口

### 新增Web API
- `GET /api/database/types` - 获取支持的数据库类型
- `GET /api/database/config` - 获取当前数据库配置
- `POST /api/database/switch` - 切换数据库类型

### 响应示例
```json
{
  "success": true,
  "types": ["doris", "postgresql"],
  "current_type": "postgresql"
}
```

## 测试验证

运行测试脚本验证功能：
```bash
python test_database_selection.py
```

测试内容包括：
- 数据库工厂功能测试
- 配置验证测试
- 连接创建测试

## 注意事项

1. **配置要求**：确保目标数据库的配置信息正确
2. **权限要求**：PostgreSQL用户需要有创建数据库和表的权限
3. **数据类型**：某些Oracle特有的数据类型可能需要手动调整
4. **性能优化**：大数据量迁移建议启用并行插入功能

## 兼容性

- **向后兼容**：现有的Doris配置和功能完全保持不变
- **平滑升级**：可以无缝从单一Doris支持升级到多数据库支持
- **配置灵活**：支持运行时切换数据库类型

## 故障排除

### 常见问题

1. **PostgreSQL连接失败**
   - 检查PostgreSQL服务是否启动
   - 验证连接参数（主机、端口、用户名、密码）
   - 确认防火墙设置

2. **数据类型转换错误**
   - 查看日志中的具体错误信息
   - 手动调整DDL语句中的数据类型
   - 参考PostgreSQL数据类型文档

3. **权限不足**
   - 确保PostgreSQL用户有足够权限
   - 检查数据库是否存在，如不存在会自动创建

### 日志查看
系统会记录详细的操作日志，包括：
- 数据库连接状态
- SQL语法转换过程
- 数据导入进度和结果

查看日志文件：`migration.log`