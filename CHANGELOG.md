# 更新日志

## [2.0.0] - 2025-01-XX - 多数据库支持版本

### 🎉 重大更新
- **多数据库支持**: 新增PostgreSQL目标数据库支持，现支持Apache Doris和PostgreSQL
- **数据库工厂模式**: 实现统一的数据库连接管理，支持运行时切换数据库类型
- **SQL语法自动转换**: 自动处理Oracle/MySQL到PostgreSQL的语法转换

### ✨ 新增功能
- **PostgreSQL连接模块** (`core/postgresql_connection.py`)
  - 完整的PostgreSQL数据库操作支持
  - 连接池管理和并行批量插入
  - 自动SQL语法转换和数据类型映射
  
- **数据库工厂类** (`core/database_factory.py`)
  - 根据配置自动选择数据库连接类型
  - 配置验证和错误处理
  - 支持的数据库类型查询

- **Web界面增强**
  - 数据库类型选择器（左侧面板）
  - 新增API接口：`/api/database/types`、`/api/database/config`、`/api/database/switch`
  - 实时数据库状态显示

### 🔧 改进优化
- **主控制器重命名**: `OracleDoriseMigrator` → `OracleToDbMigrator`
- **配置文件扩展**: 支持多数据库配置和目标类型选择
- **依赖更新**: 新增 `psycopg2-binary==2.9.7` PostgreSQL驱动

### 📚 文档更新
- **新增文档**:
  - `POSTGRESQL_SUPPORT.md` - PostgreSQL支持详细说明
  - `QUICK_START.md` - 快速启动指南
  - `MULTI_DATABASE_SUPPORT_COMPLETION.md` - 功能完成报告
  - `CHANGELOG.md` - 本更新日志

- **更新文档**:
  - `README.md` - 更新架构图和配置说明
  - `config.yaml.example` - 添加PostgreSQL配置示例

### 🧪 测试增强
- **新增测试脚本**:
  - `test_database_selection.py` - 数据库选择功能测试
  - `test_system.py` - 系统功能综合测试

### 🔄 向后兼容性
- ✅ 完全兼容现有Doris配置
- ✅ 所有原有功能保持不变
- ✅ API接口向后兼容
- ✅ 平滑升级，无需修改现有配置

### 🚀 性能提升
- **PostgreSQL连接池**: 支持8-16个并发连接，提升并行处理性能
- **批量插入优化**: 针对PostgreSQL优化的批量插入策略
- **内存使用优化**: 改进大文件处理的内存管理

---

## [1.x.x] - 历史版本

### [1.3.0] - 2024-12-XX - 性能优化版本
- 高性能SQL解析器
- 并行数据导入优化
- Web界面通信模式改进

### [1.2.0] - 2024-11-XX - Web界面增强版本
- 响应式Web界面
- 实时进度监控
- 服务器文件路径支持

### [1.1.0] - 2024-10-XX - AI推断版本
- DeepSeek AI集成
- 智能表结构推断
- 用户确认机制

### [1.0.0] - 2024-09-XX - 初始版本
- 基础Oracle到Doris迁移功能
- 命令行界面
- 基本SQL解析和导入

---

## 升级指南

### 从 1.x.x 升级到 2.0.0

1. **备份现有配置**:
   ```bash
   cp config.yaml config.yaml.backup
   ```

2. **更新代码**:
   ```bash
   git pull origin main
   pip install -r requirements.txt
   ```

3. **更新配置文件**:
   ```bash
   # 添加数据库类型选择
   database:
     target_type: "doris"  # 保持现有行为
     # 现有doris配置保持不变
   ```

4. **更新代码引用**（如果有自定义代码）:
   ```python
   # 旧版本
   from main_controller import OracleDoriseMigrator
   migrator = OracleDoriseMigrator("config.yaml")
   
   # 新版本
   from main_controller import OracleToDbMigrator
   migrator = OracleToDbMigrator("config.yaml")
   ```

5. **验证升级**:
   ```bash
   python test_system.py
   ```

### 新用户快速开始

参考 `QUICK_START.md` 获取详细的快速开始指南。

---

## 技术支持

如果在升级过程中遇到问题，请：

1. 查看 `TROUBLESHOOTING.md` 故障排除指南
2. 检查 `POSTGRESQL_SUPPORT.md` PostgreSQL相关说明
3. 运行 `python test_system.py` 进行系统诊断
4. 查看日志文件：`migration.log` 和 `web_app.log`

---

**版本说明**:
- **主版本号**: 重大功能更新或架构变更
- **次版本号**: 新功能添加
- **修订版本号**: Bug修复和小改进