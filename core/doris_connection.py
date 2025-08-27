"""
Doris数据库连接模块

负责管理与Apache Doris数据库的连接和操作
"""

import logging
import pymysql
import time
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass

@dataclass
class ExecutionResult:
    """执行结果数据类"""
    success: bool
    affected_rows: int = 0
    error_message: str = ""
    execution_time: float = 0.0

class DorisConnection:
    """Doris数据库连接管理器"""
    
    def __init__(self, config: Dict):
        """
        初始化数据库连接
        
        Args:
            config: 配置字典，包含数据库连接参数
        """
        self.config = config
        self.db_config = config.get('database', {}).get('doris', {})
        self.host = self.db_config.get('host', 'localhost')
        self.port = self.db_config.get('port', 9030)
        self.user = self.db_config.get('user', 'root')
        self.password = self.db_config.get('password', '')
        self.database = self.db_config.get('database', 'migration_db')
        self.charset = self.db_config.get('charset', 'utf8mb4')
        
        self.logger = logging.getLogger(__name__)
        self._connection = None
        
        # 测试连接
        self._test_connection()
    
    def _test_connection(self):
        """测试数据库连接"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    if result[0] == 1:
                        self.logger.info("Doris数据库连接测试成功")
                    else:
                        self.logger.warning("Doris数据库连接测试异常")
        except Exception as e:
            self.logger.error(f"Doris数据库连接失败: {str(e)}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        获取数据库连接（上下文管理器）
        
        Yields:
            数据库连接对象
        """
        connection = None
        try:
            connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset=self.charset,
                autocommit=False,
                connect_timeout=30,
                read_timeout=60,
                write_timeout=60
            )
            yield connection
        except Exception as e:
            self.logger.error(f"获取数据库连接失败: {str(e)}")
            raise
        finally:
            if connection:
                connection.close()
    
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
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 执行DDL语句
                    cursor.execute(ddl_statement)
                    conn.commit()
                    
                    execution_time = time.time() - start_time
                    
                    self.logger.info(f"表创建成功，耗时: {execution_time:.2f}秒")
                    
                    return ExecutionResult(
                        success=True,
                        affected_rows=0,  # DDL语句不返回影响行数
                        execution_time=execution_time
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"创建表失败: {str(e)}"
            self.logger.error(error_msg)
            
            return ExecutionResult(
                success=False,
                error_message=error_msg,
                execution_time=execution_time
            )
    
    def execute_batch_insert(self, sql_statements: List[str]) -> ExecutionResult:
        """
        批量执行INSERT语句
        
        Args:
            sql_statements: SQL语句列表
            
        Returns:
            执行结果
        """
        start_time = time.time()
        total_affected = 0
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for sql in sql_statements:
                        if sql.strip():
                            cursor.execute(sql)
                            total_affected += cursor.rowcount
                    
                    conn.commit()
                    
                    execution_time = time.time() - start_time
                    
                    self.logger.info(f"批量插入成功: {len(sql_statements)}条语句, {total_affected}行数据, 耗时: {execution_time:.2f}秒")
                    
                    return ExecutionResult(
                        success=True,
                        affected_rows=total_affected,
                        execution_time=execution_time
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"批量插入失败: {str(e)}"
            self.logger.error(error_msg)
            
            return ExecutionResult(
                success=False,
                affected_rows=total_affected,
                error_message=error_msg,
                execution_time=execution_time
            )
    
    def execute_single_insert(self, sql_statement: str) -> ExecutionResult:
        """
        执行单条INSERT语句
        
        Args:
            sql_statement: SQL语句
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql_statement)
                    affected_rows = cursor.rowcount
                    conn.commit()
                    
                    execution_time = time.time() - start_time
                    
                    return ExecutionResult(
                        success=True,
                        affected_rows=affected_rows,
                        execution_time=execution_time
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"执行INSERT语句失败: {str(e)}"
            
            return ExecutionResult(
                success=False,
                error_message=error_msg,
                execution_time=execution_time
            )
    
    def check_table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在
        
        Args:
            table_name: 表名
            
        Returns:
            表是否存在
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                    result = cursor.fetchone()
                    return result is not None
                    
        except Exception as e:
            self.logger.error(f"检查表存在性失败: {str(e)}")
            return False
    
    def get_table_row_count(self, table_name: str) -> int:
        """
        获取表行数
        
        Args:
            table_name: 表名
            
        Returns:
            表行数
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    result = cursor.fetchone()
                    return result[0] if result else 0
                    
        except Exception as e:
            self.logger.error(f"获取表行数失败: {str(e)}")
            return 0
    
    def get_table_info(self, table_name: str) -> Dict:
        """
        获取表信息
        
        Args:
            table_name: 表名
            
        Returns:
            表信息字典
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 获取表结构
                    cursor.execute(f"DESC {table_name}")
                    columns = cursor.fetchall()
                    
                    # 获取表行数
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row_count = cursor.fetchone()[0]
                    
                    return {
                        'table_name': table_name,
                        'columns': columns,
                        'row_count': row_count,
                        'exists': True
                    }
                    
        except Exception as e:
            self.logger.error(f"获取表信息失败: {str(e)}")
            return {
                'table_name': table_name,
                'exists': False,
                'error': str(e)
            }
    
    def drop_table(self, table_name: str) -> ExecutionResult:
        """
        删除表
        
        Args:
            table_name: 表名
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    conn.commit()
                    
                    execution_time = time.time() - start_time
                    
                    self.logger.info(f"表 {table_name} 删除成功")
                    
                    return ExecutionResult(
                        success=True,
                        execution_time=execution_time
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"删除表失败: {str(e)}"
            self.logger.error(error_msg)
            
            return ExecutionResult(
                success=False,
                error_message=error_msg,
                execution_time=execution_time
            )
    
    def execute_query(self, sql: str) -> Tuple[bool, List]:
        """
        执行查询语句
        
        Args:
            sql: 查询语句
            
        Returns:
            (是否成功, 查询结果)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    results = cursor.fetchall()
                    return True, results
                    
        except Exception as e:
            self.logger.error(f"执行查询失败: {str(e)}")
            return False, []
    
    def create_database_if_not_exists(self) -> bool:
        """
        创建数据库（如果不存在）
        
        Returns:
            是否成功
        """
        try:
            # 先连接到系统数据库
            connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                charset=self.charset
            )
            
            with connection.cursor() as cursor:
                # 创建数据库
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
                connection.commit()
                
            connection.close()
            self.logger.info(f"数据库 {self.database} 创建成功或已存在")
            return True
            
        except Exception as e:
            self.logger.error(f"创建数据库失败: {str(e)}")
            return False