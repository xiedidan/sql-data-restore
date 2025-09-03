"""
并行导入模块

负责将大型SQL文件分块并行导入到Doris数据库
"""

import os
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from queue import Queue
from .doris_connection import DorisConnection, ExecutionResult

@dataclass
class ImportTask:
    """导入任务数据类"""
    task_id: str
    file_path: str
    table_name: str
    chunk_index: int
    total_chunks: int
    sql_statements: List[str]
    status: str = "pending"  # pending, running, completed, failed

@dataclass
class ImportResult:
    """导入结果数据类"""
    task_id: str
    table_name: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_rows_imported: int
    total_execution_time: float
    success: bool
    error_messages: List[str]

class ProgressMonitor:
    """进度监控器"""
    
    def __init__(self, total_tasks: int, callback: Optional[Callable] = None):
        self.total_tasks = total_tasks
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.callback = callback
        self._lock = threading.Lock()
    
    def update_progress(self, task_result: ExecutionResult):
        """更新进度"""
        with self._lock:
            if task_result.success:
                self.completed_tasks += 1
            else:
                self.failed_tasks += 1
            
            if self.callback:
                progress_data = {
                    'total_tasks': self.total_tasks,
                    'completed_tasks': self.completed_tasks,
                    'failed_tasks': self.failed_tasks,
                    'progress_percent': (self.completed_tasks + self.failed_tasks) / self.total_tasks * 100
                }
                self.callback(progress_data)
    
    def get_progress(self) -> Dict:
        """获取当前进度"""
        with self._lock:
            return {
                'total_tasks': self.total_tasks,
                'completed_tasks': self.completed_tasks,
                'failed_tasks': self.failed_tasks,
                'progress_percent': (self.completed_tasks + self.failed_tasks) / self.total_tasks * 100
            }

class ParallelImporter:
    """并行导入器"""
    
    def __init__(self, config: Dict, progress_callback: Optional[Callable] = None):
        """
        初始化并行导入器
        
        Args:
            config: 配置字典
            progress_callback: 进度回调函数
        """
        self.config = config
        migration_config = config.get('migration', {})
        self.chunk_size_mb = migration_config.get('chunk_size_mb', 30)
        self.max_workers = migration_config.get('max_workers', 8)
        self.batch_size = migration_config.get('batch_size', 1000)
        self.retry_count = migration_config.get('retry_count', 3)
        self.temp_dir = migration_config.get('temp_dir', './temp')
        
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)
        
        # 确保临时目录存在
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def split_sql_file(self, file_path: str, table_name: str) -> List[str]:
        """
        分割SQL文件为多个块
        
        Args:
            file_path: SQL文件路径
            table_name: 表名
            
        Returns:
            分割后的文件路径列表
        """
        chunk_files = []
        chunk_size_bytes = self.chunk_size_mb * 1024 * 1024
        
        try:
            file_size = os.path.getsize(file_path)
            estimated_chunks = max(1, file_size // chunk_size_bytes)
            
            self.logger.info(f"开始分割SQL文件: {file_path}, 文件大小: {file_size/1024/1024:.2f}MB, 估计分块数: {estimated_chunks}")
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                chunk_index = 0
                current_chunk_size = 0
                current_chunk_lines = []
                
                for line in f:
                    line_size = len(line.encode('utf-8'))
                    
                    # 检查是否需要创建新块
                    if current_chunk_size + line_size > chunk_size_bytes and current_chunk_lines:
                        # 保存当前块
                        chunk_file = self._save_chunk(table_name, chunk_index, current_chunk_lines)
                        chunk_files.append(chunk_file)
                        
                        # 重置块状态
                        chunk_index += 1
                        current_chunk_size = 0
                        current_chunk_lines = []
                    
                    current_chunk_lines.append(line)
                    current_chunk_size += line_size
                
                # 保存最后一个块
                if current_chunk_lines:
                    chunk_file = self._save_chunk(table_name, chunk_index, current_chunk_lines)
                    chunk_files.append(chunk_file)
            
            self.logger.info(f"SQL文件分割完成: {len(chunk_files)}个块")
            return chunk_files
            
        except Exception as e:
            self.logger.error(f"分割SQL文件失败: {str(e)}")
            raise
    
    def import_chunk_parallel(self, table_name: str, chunk_files: List[str]) -> ImportResult:
        """
        并行导入文件块
        
        Args:
            table_name: 表名
            chunk_files: 文件块路径列表
            
        Returns:
            导入结果
        """
        start_time = time.time()
        
        # 创建导入任务
        tasks = []
        for i, chunk_file in enumerate(chunk_files):
            task = ImportTask(
                task_id=f"{table_name}_chunk_{i}",
                file_path=chunk_file,
                table_name=table_name,
                chunk_index=i,
                total_chunks=len(chunk_files),
                sql_statements=self._load_chunk_statements(chunk_file)
            )
            tasks.append(task)
        
        # 初始化进度监控
        monitor = ProgressMonitor(len(tasks), self.progress_callback)
        
        # 并行执行导入
        completed_tasks = 0
        failed_tasks = 0
        total_rows = 0
        error_messages = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_task = {
                executor.submit(self._import_single_chunk, task): task 
                for task in tasks
            }
            
            # 收集结果
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    monitor.update_progress(result)
                    
                    if result.success:
                        completed_tasks += 1
                        total_rows += result.affected_rows
                        self.logger.info(f"块导入成功: {task.task_id}, 导入行数: {result.affected_rows}")
                    else:
                        failed_tasks += 1
                        error_messages.append(f"块 {task.task_id}: {result.error_message}")
                        self.logger.error(f"块导入失败: {task.task_id}, 错误: {result.error_message}")
                        
                except Exception as exc:
                    failed_tasks += 1
                    error_msg = f"块 {task.task_id} 执行异常: {str(exc)}"
                    error_messages.append(error_msg)
                    self.logger.error(error_msg)
        
        # 清理临时文件
        self._cleanup_chunks(chunk_files)
        
        total_time = time.time() - start_time
        success = failed_tasks == 0
        
        result = ImportResult(
            task_id=f"{table_name}_import",
            table_name=table_name,
            total_tasks=len(tasks),
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            total_rows_imported=total_rows,
            total_execution_time=total_time,
            success=success,
            error_messages=error_messages
        )
        
        self.logger.info(f"并行导入完成: 表={table_name}, 成功={completed_tasks}, 失败={failed_tasks}, 总行数={total_rows}, 耗时={total_time:.2f}秒")
        
        return result
    
    def import_data_with_retry(self, table_name: str, sql_file: str) -> ImportResult:
        """
        带重试机制的数据导入
        
        Args:
            table_name: 表名
            sql_file: SQL文件路径
            
        Returns:
            导入结果
        """
        for attempt in range(self.retry_count):
            try:
                self.logger.info(f"开始导入数据 (尝试 {attempt + 1}/{self.retry_count}): {table_name}")
                
                # 分割文件
                chunk_files = self.split_sql_file(sql_file, table_name)
                
                # 并行导入
                result = self.import_chunk_parallel(table_name, chunk_files)
                
                if result.success or attempt == self.retry_count - 1:
                    return result
                else:
                    self.logger.warning(f"导入失败，准备重试: {table_name}")
                    time.sleep(2 ** attempt)  # 指数退避
                    
            except Exception as e:
                self.logger.error(f"导入数据异常 (尝试 {attempt + 1}): {str(e)}")
                if attempt == self.retry_count - 1:
                    return ImportResult(
                        task_id=f"{table_name}_import",
                        table_name=table_name,
                        total_tasks=0,
                        completed_tasks=0,
                        failed_tasks=1,
                        total_rows_imported=0,
                        total_execution_time=0,
                        success=False,
                        error_messages=[str(e)]
                    )
                time.sleep(2 ** attempt)
    
    def monitor_import_progress(self, table_name: str) -> Dict:
        """
        监控导入进度
        
        Args:
            table_name: 表名
            
        Returns:
            进度信息
        """
        # 这里可以实现实时进度监控逻辑
        # 当前返回基础信息
        return {
            'table_name': table_name,
            'status': 'monitoring',
            'timestamp': time.time()
        }
    
    def _save_chunk(self, table_name: str, chunk_index: int, lines: List[str]) -> str:
        """保存文件块"""
        chunk_filename = f"{table_name}_chunk_{chunk_index:04d}.sql"
        chunk_path = os.path.join(self.temp_dir, chunk_filename)
        
        with open(chunk_path, 'w', encoding='utf-8') as f:
            for line in lines:
                f.write(line)
        
        return chunk_path
    
    def _load_chunk_statements(self, chunk_file: str) -> List[str]:
        """加载块文件中的SQL语句"""
        statements = []
        
        try:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                current_statement = ""
                
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 过滤无效的SQL语句
                    if self._is_valid_sql_line(line):
                        current_statement += line + " "
                        
                        # 检查语句是否完整（以分号结尾）
                        if line.endswith(';'):
                            cleaned_statement = self._clean_sql_statement(current_statement.strip())
                            if cleaned_statement:
                                statements.append(cleaned_statement)
                            current_statement = ""
                
                # 添加最后一个语句（如果没有分号结尾）
                if current_statement.strip():
                    cleaned_statement = self._clean_sql_statement(current_statement.strip())
                    if cleaned_statement:
                        statements.append(cleaned_statement)
                    
        except Exception as e:
            self.logger.error(f"加载块文件失败: {chunk_file}, 错误: {str(e)}")
        
        return statements
    
    def _is_valid_sql_line(self, line: str) -> bool:
        """检查是否为有效的SQL行"""
        line_upper = line.upper().strip()
        
        # 过滤注释行
        if line_upper.startswith('--') or line_upper.startswith('/*') or line_upper.startswith('*/'):
            return False
            
        # 过滤空行
        if not line_upper:
            return False
            
        # 过滤包含不支持关键字的行
        invalid_keywords = ['PROMPT', 'SET ', 'SPOOL', 'WHENEVER', 'EXECUTE', 'COMMIT;', 'REM ']
        for keyword in invalid_keywords:
            if line_upper.startswith(keyword):
                return False
                
        return True
    
    def _clean_sql_statement(self, statement: str) -> str:
        """清理SQL语句，移除不支持的内容"""
        if not statement:
            return ""
            
        # 移除常见的Oracle特有内容
        lines = statement.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            line_upper = line.upper()
            
            # 过滤不支持的语句
            skip_line = False
            invalid_patterns = [
                'PROMPT ', 'SET ', 'SPOOL ', 'WHENEVER ', 'EXECUTE ', 
                'REM ', '@', 'DEFINE ', 'UNDEFINE ', 'COLUMN ',
                'TTITLE ', 'BTITLE ', 'BREAK ', 'COMPUTE '
            ]
            
            for pattern in invalid_patterns:
                if line_upper.startswith(pattern):
                    skip_line = True
                    break
                    
            if not skip_line:
                cleaned_lines.append(line)
        
        cleaned_statement = ' '.join(cleaned_lines)
        
        # 确保只包含INSERT语句
        if cleaned_statement.upper().strip().startswith('INSERT'):
            return cleaned_statement
        else:
            return ""
    
    def _import_single_chunk(self, task: ImportTask) -> ExecutionResult:
        """导入单个文件块"""
        try:
            # 创建数据库连接
            db_conn = DorisConnection(self.config)
            
            # 批量执行SQL语句
            if task.sql_statements:
                result = db_conn.execute_batch_insert(task.sql_statements)
                task.status = "completed" if result.success else "failed"
                return result
            else:
                return ExecutionResult(
                    success=True,
                    affected_rows=0,
                    execution_time=0
                )
                
        except Exception as e:
            task.status = "failed"
            return ExecutionResult(
                success=False,
                error_message=str(e),
                execution_time=0
            )
    
    def _cleanup_chunks(self, chunk_files: List[str]):
        """清理临时文件块"""
        for chunk_file in chunk_files:
            try:
                if os.path.exists(chunk_file):
                    os.remove(chunk_file)
            except Exception as e:
                self.logger.warning(f"清理临时文件失败: {chunk_file}, 错误: {str(e)}")
    
    def handle_import_errors(self, failed_chunks: List[str], table_name: str) -> bool:
        """
        处理导入错误，重试失败的块
        
        Args:
            failed_chunks: 失败的块文件列表
            table_name: 表名
            
        Returns:
            是否成功处理所有错误
        """
        if not failed_chunks:
            return True
        
        self.logger.info(f"开始处理失败的块: {len(failed_chunks)}个")
        
        success_count = 0
        for chunk_file in failed_chunks:
            try:
                # 重新加载并导入失败的块
                statements = self._load_chunk_statements(chunk_file)
                db_conn = DorisConnection(self.config)
                result = db_conn.execute_batch_insert(statements)
                
                if result.success:
                    success_count += 1
                    self.logger.info(f"重试成功: {chunk_file}")
                else:
                    self.logger.error(f"重试失败: {chunk_file}, 错误: {result.error_message}")
                    
            except Exception as e:
                self.logger.error(f"重试异常: {chunk_file}, 错误: {str(e)}")
        
        return success_count == len(failed_chunks)