# 数据库名称替换修复报告

## 🎯 问题描述

用户报告错误：`Database [EMR_HIS] does not exist`

### 错误分析
根据日志信息显示：
- AI推断成功生成DDL语句
- 表创建成功（表明DDL语句本身没有数据库名称问题）
- 在数据导入过程中出现错误：`Database [EMR_HIS] does not exist`
- 错误原因：INSERT语句中仍然包含原始Oracle数据库名称`EMR_HIS`，而Doris配置使用的是`migration_db`

## 🔧 修复方案

### 1. AI推断提示词优化

**文件**: `core/schema_inference.py`

#### 修改推断提示词
```python
prompt += """
请根据以上INSERT语句中的数据，推断出合适的字段类型和约束，生成Doris的CREATE TABLE语句。

要求:
1. 严格遵循Apache Doris的DDL语法
2. 合理推断字段类型（VARCHAR、INT、BIGINT、DECIMAL、DATE、DATETIME等）
3. 设置合适的字段长度
4. 添加必要的主键或分布列（Duplicate Key模型）
5. 考虑数据的业务含义选择合适的类型
6. 请只返回CREATE TABLE语句，不要包含额外的解释
7. 重要：不要在DDL语句中包含任何数据库名称，只创建表结构
8. 不要使用USE语句或数据库限定符

请直接返回DDL语句:
"""
```

#### 添加DDL语句清理功能
```python
def _clean_database_references(self, ddl_statement: str) -> str:
    """
    清理DDL语句中的数据库名称引用
    
    Args:
        ddl_statement: 原始DDL语句
        
    Returns:
        清理后的DDL语句
    """
    if not ddl_statement:
        return ddl_statement
        
    # 移除USE语句
    ddl_statement = re.sub(r'USE\s+\w+\s*;?\s*', '', ddl_statement, flags=re.IGNORECASE)
    
    # 移除数据库名称限定符（如 database.table_name）
    # 保留表名，移除数据库前缀
    ddl_statement = re.sub(r'CREATE\s+TABLE\s+\w+\.', 'CREATE TABLE ', ddl_statement, flags=re.IGNORECASE)
    
    # 移除常见的Oracle数据库名称引用
    oracle_db_patterns = [
        r'\[?EMR_HIS\]?\.',  # [EMR_HIS].table_name 或 EMR_HIS.table_name
        r'EMR_HIS\s*\.',      # EMR_HIS .table_name
        r'\[EMR_HIS\]',       # [EMR_HIS]
    ]
    
    for pattern in oracle_db_patterns:
        ddl_statement = re.sub(pattern, '', ddl_statement, flags=re.IGNORECASE)
    
    # 清理多余的空格
    ddl_statement = re.sub(r'\s+', ' ', ddl_statement)
    ddl_statement = ddl_statement.strip()
    
    return ddl_statement
```

### 2. 数据库连接器清理

**文件**: `core/doris_connection.py`

#### 修改create_table方法
```python
def create_table(self, ddl_statement: str) -> ExecutionResult:
    """
    创建表
    
    Args:
        ddl_statement: DDL语句
        
    Returns:
        执行结果
    """
    start_time = time.time()
    
    try:
        # 清理DDL语句中的数据库名称引用
        cleaned_ddl = self._clean_ddl_database_references(ddl_statement)
        
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # 执行清理后的DDL语句
                cursor.execute(cleaned_ddl)
                conn.commit()
                # ... rest of the method
```

#### 修改execute_batch_insert方法
```python
def execute_batch_insert(self, sql_statements: List[str]) -> ExecutionResult:
    """
    批量执行INSERT语句
    """
    try:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                for sql in sql_statements:
                    if sql.strip():
                        # 清理INSERT语句中的数据库名称引用
                        cleaned_sql = self._clean_insert_database_references(sql)
                        cursor.execute(cleaned_sql)
                        total_affected += cursor.rowcount
                # ... rest of the method
```

#### 添加INSERT语句清理功能
```python
def _clean_insert_database_references(self, insert_statement: str) -> str:
    """
    清理INSERT语句中的数据库名称引用
    """
    if not insert_statement:
        return insert_statement
        
    import re
    
    # 移除数据库名称限定符（如 database.table_name）
    # 保留表名，移除数据库前缀
    insert_statement = re.sub(r'INSERT\s+INTO\s+\w+\.', 'INSERT INTO ', insert_statement, flags=re.IGNORECASE)
    
    # 移除常见的Oracle数据库名称引用
    oracle_db_patterns = [
        r'\[?EMR_HIS\]?\.',  # [EMR_HIS].table_name 或 EMR_HIS.table_name
        r'EMR_HIS\s*\.',      # EMR_HIS .table_name
        r'\[EMR_HIS\]',       # [EMR_HIS]
    ]
    
    for pattern in oracle_db_patterns:
        insert_statement = re.sub(pattern, '', insert_statement, flags=re.IGNORECASE)
    
    # 清理多余的空格
    insert_statement = re.sub(r'\s+', ' ', insert_statement)
    insert_statement = insert_statement.strip()
    
    return insert_statement
```

### 3. 并行导入器清理

**文件**: `core/parallel_importer.py`

#### 修改SQL清理逻辑
```python
def _clean_sql_statement(self, statement: str) -> str:
    """清理SQL语句，移除不支持的内容"""
    if not statement:
        return ""
        
    # ... existing cleaning logic ...
    
    # 确保只包含INSERT语句
    if cleaned_statement.upper().strip().startswith('INSERT'):
        # 清理数据库名称引用
        cleaned_statement = self._clean_database_references_in_insert(cleaned_statement)
        return cleaned_statement
    else:
        return ""
```

## 📊 修复效果

### 修复前
```
错误: Database [EMR_HIS] does not exist
原因: INSERT语句包含原始Oracle数据库名称引用
示例: INSERT INTO EMR_HIS.ZYZXSRTJ (...)
```

### 修复后
```
正常: 使用配置的Doris数据库名称
结果: INSERT语句只包含表名，不包含数据库前缀
示例: INSERT INTO ZYZXSRTJ (...)
```

## 🚀 修复策略

1. **多层清理机制**：
   - AI推断阶段：优化提示词，要求不包含数据库名称
   - DDL处理阶段：清理生成的DDL语句
   - INSERT处理阶段：清理每条INSERT语句

2. **全面的模式匹配**：
   - 支持各种Oracle数据库名称格式：`[EMR_HIS]`、`EMR_HIS.`、`EMR_HIS .`
   - 移除USE语句和数据库限定符
   - 保留表名，只移除数据库前缀

3. **健壮的错误处理**：
   - 在多个关键节点进行清理
   - 确保即使AI生成包含数据库名称的语句也能正确处理

## 🔍 技术实现

```
AI推断 → DDL清理 → 表创建 → SQL分割 → INSERT清理 → 数据导入
   ↓         ↓         ↓         ↓          ↓          ↓
移除DB名   移除DB名   使用配置   分块处理    移除DB名   成功导入
```

## 📝 测试验证

1. **重启Web应用**：`python app.py --mode web`
2. **重新处理ZYZXSRTJ表**：使用服务器文件路径功能
3. **检查DDL语句**：确认不包含`EMR_HIS`引用
4. **监控导入过程**：确认INSERT语句正确执行
5. **验证数据导入**：检查Doris数据库中的数据

## ✅ 预期效果

- ✅ AI推断生成的DDL语句不包含数据库名称
- ✅ INSERT语句自动清理数据库前缀
- ✅ 数据成功导入到配置的Doris数据库
- ✅ 不再出现"Database [EMR_HIS] does not exist"错误
- ✅ 支持处理各种Oracle数据库名称格式

## 🎉 总结

本次修复实现了全面的数据库名称清理机制，确保：
1. **AI推断阶段**：通过优化提示词避免生成包含数据库名称的DDL
2. **DDL处理阶段**：自动清理任何残留的数据库名称引用
3. **数据导入阶段**：确保INSERT语句使用正确的表名格式

这样可以彻底解决Oracle数据库名称与Doris配置不匹配的问题，确保数据迁移过程的顺利进行。