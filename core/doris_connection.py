"""
Doris数据库连接模块

负责管理与Apache Doris数据库的连接和操作，支持并行连接池
"""

import logging
import pymysql
import time
import threading
import queue
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

@dataclass
class ExecutionResult:
    """执行结果数据类"""
    success: bool
    affected_rows: int = 0
    error_message: str = ""
    execution_time: float = 0.0

class DorisConnectionPool:
    """
    Doris数据库连接池管理器
    支持并行连接和高性能批量插入
    """
    
    def __init__(self, config: Dict, pool_size: int = None):
        """
        初始化连接池
        
        Args:
            config: 配置字典
            pool_size: 连接池大小，默认为max_workers配置
        """
        self.config = config
        self.db_config = config.get('database', {}).get('doris', {})
        self.host = self.db_config.get('host', 'localhost')
        self.port = self.db_config.get('port', 9030)
        self.user = self.db_config.get('user', 'root')
        self.password = self.db_config.get('password', '')
        self.database = self.db_config.get('database', 'migration_db')
        self.charset = self.db_config.get('charset', 'utf8mb4')
        
        # 性能配置
        migration_config = config.get('migration', {})
        self.pool_size = pool_size or migration_config.get('max_workers', 8)
        self.batch_size = migration_config.get('batch_size', 1000)
        self.max_retries = migration_config.get('retry_count', 3)
        
        self.logger = logging.getLogger(__name__)
        self._pool = queue.Queue(maxsize=self.pool_size)
        self._lock = threading.Lock()
        self._created_connections = 0
        
        # 初始化连接池
        self._initialize_pool()
        
    def _initialize_pool(self):
        """初始化连接池"""
        try:
            # 创建初始连接
            for _ in range(min(2, self.pool_size)):  # 先创建2个连接
                connection = self._create_connection()
                self._pool.put(connection)
                self._created_connections += 1
            
            self.logger.info(f"连接池初始化成功，初始连接数: {self._created_connections}/{self.pool_size}")
            
            # 测试连接
            self._test_connection()
            
        except Exception as e:
            self.logger.error(f"连接池初始化失败: {str(e)}")
            raise
    
    def _create_connection(self):
        """创建新的数据库连接"""
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset=self.charset,
            autocommit=False,
            connect_timeout=30,
            read_timeout=300,  # 增加读取超时
            write_timeout=300,  # 增加写入超时
            # 优化TCP参数
            init_command="SET SESSION wait_timeout=3600, interactive_timeout=3600"
        )
    
    @contextmanager
    def get_connection(self):
        """从连接池获取连接"""
        connection = None
        try:
            # 尝试从池中获取连接
            try:
                connection = self._pool.get_nowait()
            except queue.Empty:
                # 如果池为空且未达到最大连接数，创建新连接
                with self._lock:
                    if self._created_connections < self.pool_size:
                        connection = self._create_connection()
                        self._created_connections += 1
                        self.logger.debug(f"创建新连接，当前连接数: {self._created_connections}")
                    else:
                        # 等待连接可用
                        connection = self._pool.get(timeout=30)
            
            # 检查连接是否有效
            if not self._is_connection_alive(connection):
                connection.close()
                connection = self._create_connection()
                self.logger.debug("连接已失效，重新创建")
            
            yield connection
            
        except Exception as e:
            self.logger.error(f"获取数据库连接失败: {str(e)}")
            if connection:
                try:
                    connection.close()
                except:
                    pass
                connection = None
            raise
        finally:
            if connection:
                try:
                    # 将连接放回池中
                    self._pool.put_nowait(connection)
                except queue.Full:
                    # 如果池已满，关闭连接
                    connection.close()
    
    def _is_connection_alive(self, connection) -> bool:
        """检查连接是否活跃"""
        try:
            connection.ping(reconnect=False)
            return True
        except:
            return False
    
    def _test_connection(self):
        """测试连接池"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    if result[0] == 1:
                        self.logger.info("Doris连接池测试成功")
                    else:
                        self.logger.warning("Doris连接池测试异常")
        except Exception as e:
            self.logger.error(f"Doris连接池测试失败: {str(e)}")
            raise
    
    def execute_parallel_batch_insert(self, sql_batches: List[List[str]], progress_callback: Optional[callable] = None) -> ExecutionResult:
        """
        并行执行批量插入
        
        Args:
            sql_batches: SQL语句批次列表
            progress_callback: 进度回调函数
            
        Returns:
            执行结果
        """
        start_time = time.time()
        total_affected = 0
        errors = []
        
        # 使用线程池并行执行
        max_workers = min(len(sql_batches), self.pool_size, self.pool_size)
        
        self.logger.info(f"开始并行批量插入: {len(sql_batches)}个批次, {max_workers}个工作线程")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有批次任务
            future_to_batch = {
                executor.submit(self._execute_batch, batch, batch_idx): batch_idx 
                for batch_idx, batch in enumerate(sql_batches)
            }
            
            completed_batches = 0
            # 收集结果
            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    result = future.result()
                    if result.success:
                        total_affected += result.affected_rows
                        self.logger.debug(f"批次 {batch_idx} 执行成功: {result.affected_rows} 行")
                    else:
                        errors.append(f"批次 {batch_idx}: {result.error_message}")
                        self.logger.error(f"批次 {batch_idx} 执行失败: {result.error_message}")
                    
                    completed_batches += 1
                    
                    # 回调进度
                    if progress_callback:
                        progress_callback({
                            'completed_batches': completed_batches,
                            'total_batches': len(sql_batches),
                            'total_affected_rows': total_affected,
                            'progress_percent': (completed_batches / len(sql_batches)) * 100
                        })
                        
                except Exception as exc:
                    error_msg = f"批次 {batch_idx} 执行异常: {str(exc)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
                    completed_batches += 1
        
        execution_time = time.time() - start_time
        success = len(errors) == 0
        
        self.logger.info(f"并行批量插入完成: 耗时 {execution_time:.2f}秒, 影响行数 {total_affected}, 错误数 {len(errors)}")
        
        return ExecutionResult(
            success=success,
            affected_rows=total_affected,
            execution_time=execution_time,
            error_message="; ".join(errors) if errors else ""
        )
    
    def _execute_batch(self, sql_statements: List[str], batch_idx: int) -> ExecutionResult:
        """执行单个批次的SQL语句"""
        start_time = time.time()
        affected_rows = 0
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for sql in sql_statements:
                        if sql.strip():
                            # 清理INSERT语句中的数据库名称引用
                            cleaned_sql = self._clean_insert_database_references(sql)
                            cursor.execute(cleaned_sql)
                            affected_rows += cursor.rowcount
                    
                    conn.commit()
                    
                    execution_time = time.time() - start_time
                    
                    return ExecutionResult(
                        success=True,
                        affected_rows=affected_rows,
                        execution_time=execution_time
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"批次 {batch_idx} 执行失败: {str(e)}"
            
            return ExecutionResult(
                success=False,
                affected_rows=affected_rows,
                error_message=error_msg,
                execution_time=execution_time
            )
    
    def _clean_insert_database_references(self, insert_statement: str) -> str:
        """清理INSERT语句中的数据库名称引用"""
        if not insert_statement:
            return insert_statement
            
        import re
        
        # 移除数据库名称限定符
        insert_statement = re.sub(r'INSERT\s+INTO\s+\w+\.', 'INSERT INTO ', insert_statement, flags=re.IGNORECASE)
        
        # 移除常见的Oracle数据库名称引用
        oracle_db_patterns = [
            r'\[?EMR_HIS\]?\.',
            r'EMR_HIS\s*\.',
            r'\[EMR_HIS\]',
        ]
        
        for pattern in oracle_db_patterns:
            insert_statement = re.sub(pattern, '', insert_statement, flags=re.IGNORECASE)
        
        # 清理多余的空格
        insert_statement = re.sub(r'\s+', ' ', insert_statement)
        insert_statement = insert_statement.strip()
        
        return insert_statement
    
    def close_all_connections(self):
        """关闭所有连接"""
        closed_count = 0
        while not self._pool.empty():
            try:
                connection = self._pool.get_nowait()
                connection.close()
                closed_count += 1
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"关闭连接失败: {str(e)}")
        
        self.logger.info(f"连接池已关闭，关闭了 {closed_count} 个连接")


class DorisConnection:
    """Doris数据库连接管理器"""
    
    def __init__(self, config: Dict, use_connection_pool: bool = True):
        """
        初始化数据库连接
        
        Args:
            config: 配置字典，包含数据库连接参数
            use_connection_pool: 是否使用连接池
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
        
        # 连接池支持
        self.use_connection_pool = use_connection_pool
        self._connection_pool = None
        
        if self.use_connection_pool:
            # 创建连接池
            self._connection_pool = DorisConnectionPool(config)
            self.logger.info("使用连接池模式")
        else:
            # 测试单一连接
            self._test_connection()
            self.logger.info("使用单一连接模式")
    
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
        if self.use_connection_pool and self._connection_pool:
            # 使用连接池
            with self._connection_pool.get_connection() as conn:
                yield conn
        else:
            # 使用单一连接
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
    
    def create_table(self, ddl_statement: str, drop_if_exists: bool = False) -> ExecutionResult:
        """
        创建表
        
        Args:
            ddl_statement: DDL语句
            drop_if_exists: 如果表已存在是否删除重建
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        try:
            # 清理DDL语句中的数据库名称引用
            cleaned_ddl = self._clean_ddl_database_references(ddl_statement)
            
            # 提取表名
            table_name = self._extract_table_name_from_ddl(cleaned_ddl)
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 检查表是否已存在
                    if table_name and self.check_table_exists(table_name):
                        if drop_if_exists:
                            self.logger.info(f"表 {table_name} 已存在，正在删除重建...")
                            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                            conn.commit()
                        else:
                            self.logger.warning(f"表 {table_name} 已存在，跳过创建")
                            return ExecutionResult(
                                success=True,
                                affected_rows=0,
                                execution_time=time.time() - start_time,
                                error_message=f"表 {table_name} 已存在"
                            )
                    
                    # 执行清理后的DDL语句
                    cursor.execute(cleaned_ddl)
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
    
    def execute_batch_insert(self, sql_statements: List[str], use_parallel: bool = True) -> ExecutionResult:
        """
        批量执行INSERT语句
        
        Args:
            sql_statements: SQL语句列表
            use_parallel: 是否使用并行执行
            
        Returns:
            执行结果
        """
        if self.use_connection_pool and self._connection_pool and use_parallel and len(sql_statements) > 100:
            # 使用并行批量插入
            return self._execute_parallel_batch_insert(sql_statements)
        else:
            # 使用传统批量插入
            return self._execute_traditional_batch_insert(sql_statements)
    
    def _execute_parallel_batch_insert(self, sql_statements: List[str]) -> ExecutionResult:
        """并行批量插入"""
        # 将SQL语句分批
        batch_size = self.config.get('migration', {}).get('batch_size', 1000)
        sql_batches = []
        
        for i in range(0, len(sql_statements), batch_size):
            batch = sql_statements[i:i + batch_size]
            sql_batches.append(batch)
        
        self.logger.info(f"使用并行批量插入: {len(sql_statements)}条语句分为{len(sql_batches)}个批次")
        
        return self._connection_pool.execute_parallel_batch_insert(sql_batches)
    
    def _execute_traditional_batch_insert(self, sql_statements: List[str]) -> ExecutionResult:
        """传统批量插入"""
        start_time = time.time()
        total_affected = 0
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for sql in sql_statements:
                        if sql.strip():
                            # 清理INSERT语句中的数据库名称引用
                            cleaned_sql = self._clean_insert_database_references(sql)
                            cursor.execute(cleaned_sql)
                            total_affected += cursor.rowcount
                    
                    conn.commit()
                    
                    execution_time = time.time() - start_time
                    
                    self.logger.info(f"传统批量插入成功: {len(sql_statements)}条语句, {total_affected}行数据, 耗时: {execution_time:.2f}秒")
                    
                    return ExecutionResult(
                        success=True,
                        affected_rows=total_affected,
                        execution_time=execution_time
                    )
                    
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"传统批量插入失败: {str(e)}"
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
    
    def _clean_ddl_database_references(self, ddl_statement: str) -> str:
        """
        清理DDL语句中的数据库名称引用
        
        Args:
            ddl_statement: 原始DDL语句
            
        Returns:
            清理后的DDL语句
        """
        if not ddl_statement:
            return ddl_statement
            
        import re
        
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
        
        self.logger.debug(f"DDL语句清理完成")
        return ddl_statement
    
    def _clean_insert_database_references(self, insert_statement: str) -> str:
        """
        清理INSERT语句中的数据库名称引用
        
        Args:
            insert_statement: 原始INSERT语句
            
        Returns:
            清理后的INSERT语句
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
    
    def _extract_table_name_from_ddl(self, ddl_statement: str) -> str:
        """
        从 DDL 语句中提取表名
        
        Args:
            ddl_statement: DDL语句
            
        Returns:
            表名
        """
        if not ddl_statement:
            return ""
            
        import re
        
        # 匹配 CREATE TABLE table_name 模式
        match = re.search(r'CREATE\s+TABLE\s+(\w+)', ddl_statement, re.IGNORECASE)
        if match:
            return match.group(1)
            
        return ""
    
    def check_table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在
        
        Args:
            table_name: 表名
            
        Returns:
            是否存在
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
    
    def close(self):
        """关闭连接或连接池"""
        if self.use_connection_pool and self._connection_pool:
            self._connection_pool.close_all_connections()
        # 单一连接模式下，连接在上下文管理器中自动关闭