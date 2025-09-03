"""
主控制器模块

整合所有功能模块，提供统一的迁移接口
"""

import os
import sys
import logging
import time
import yaml
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

# 尝试相对导入，如果失败则使用绝对导入
try:
    from .core.sql_parser import SQLFileParser, TableSchema
    from .core.schema_inference import SchemaInferenceEngine, InferenceResult
    from .core.doris_connection import DorisConnection, ExecutionResult
    from .core.parallel_importer import ParallelImporter, ImportResult
except ImportError:
    # 添加项目根目录到路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    from core.sql_parser import SQLFileParser, TableSchema
    from core.schema_inference import SchemaInferenceEngine, InferenceResult
    from core.doris_connection import DorisConnection, ExecutionResult
    from core.parallel_importer import ParallelImporter, ImportResult

@dataclass
class MigrationTask:
    """迁移任务数据类"""
    task_id: str
    sql_file: str
    table_name: str
    status: str = "pending"  # pending, parsing, inferring, waiting_confirm, confirmed, importing, completed, failed
    sample_data: Dict = None
    inference_result: InferenceResult = None
    ddl_statement: str = ""
    import_result: ImportResult = None
    created_at: float = 0
    completed_at: float = 0
    error_message: str = ""

class OracleDoriseMigrator:
    """Oracle到Doris迁移器主控制器"""
    
    def __init__(self, config_path: str = "config.yaml", migration_config: Optional[Dict] = None):
        """
        初始化迁移器
        
        Args:
            config_path: 配置文件路径
            migration_config: 自定义迁移配置
        """
        # 加载配置
        self.config = self._load_config(config_path)
        if migration_config:
            self.config.setdefault('migration', {}).update(migration_config)
        
        # 初始化核心组件
        self.sql_parser = SQLFileParser(self.config)
        self.schema_engine = SchemaInferenceEngine(self.config)
        self.db_connection = DorisConnection(self.config)
        
        # 任务管理
        self.tasks = {}
        self.active_task = None
        
        # 回调函数
        self.progress_callback = None
        self.error_callback = None
        self.completion_callback = None
        
        # 设置日志
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # 确保数据库存在
        self.db_connection.create_database_if_not_exists()
        
        self.logger.info("Oracle到Doris迁移器初始化完成")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config
        except Exception as e:
            print(f"警告：加载配置文件失败 ({e})，使用默认配置")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'database': {
                'doris': {
                    'host': 'localhost',
                    'port': 9030,
                    'user': 'root',
                    'password': '',
                    'database': 'migration_db'
                }
            },
            'deepseek': {
                'api_key': 'your_api_key_here',
                'base_url': 'https://api.deepseek.com',
                'model': 'deepseek-reasoner'
            },
            'migration': {
                'sample_lines': 100,
                'max_workers': 8,
                'chunk_size_mb': 30,
                'batch_size': 1000,
                'retry_count': 3,
                'enable_user_confirmation': True
            }
        }
    
    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.get('logging', {})
        level = getattr(logging, log_config.get('level', 'INFO'))
        
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(
                    log_config.get('file', 'migration.log'),
                    encoding='utf-8'
                )
            ]
        )
    
    def enable_monitoring(self, 
                         progress_callback: Optional[Callable] = None,
                         error_callback: Optional[Callable] = None,
                         completion_callback: Optional[Callable] = None):
        """
        启用监控回调
        
        Args:
            progress_callback: 进度回调函数
            error_callback: 错误回调函数
            completion_callback: 完成回调函数
        """
        self.progress_callback = progress_callback
        self.error_callback = error_callback
        self.completion_callback = completion_callback
    
    def infer_schema(self, sql_file: str, task_id: Optional[str] = None) -> TableSchema:
        """
        推断表结构
        
        Args:
            sql_file: SQL文件路径
            task_id: 任务ID（可选）
            
        Returns:
            表结构对象
        """
        if task_id is None:
            task_id = f"task_{int(time.time())}"
        
        try:
            # 创建任务
            task = MigrationTask(
                task_id=task_id,
                sql_file=sql_file,
                table_name="",
                status="parsing",
                created_at=time.time()
            )
            self.tasks[task_id] = task
            self.active_task = task
            
            self.logger.info(f"开始推断表结构: {sql_file}")
            
            # 1. 解析SQL文件
            self._update_progress("正在解析SQL文件...")
            sample_data = self.sql_parser.extract_sample_data(sql_file)
            task.sample_data = sample_data
            task.table_name = sample_data.get('table_name', 'unknown_table')
            task.status = "inferring"
            
            self.logger.info(f"SQL文件解析完成，表名: {task.table_name}")
            
            # 2. AI推断表结构
            self._update_progress("正在推断表结构...")
            inference_result = self.schema_engine.infer_table_schema(sample_data)
            task.inference_result = inference_result
            task.ddl_statement = inference_result.ddl_statement
            
            if inference_result.success:
                task.status = "waiting_confirm"
                self.logger.info(f"表结构推断成功: {task.table_name}")
            else:
                task.status = "failed"
                task.error_message = inference_result.error_message
                self.logger.error(f"表结构推断失败: {inference_result.error_message}")
                if self.error_callback:
                    self.error_callback(f"推断失败: {inference_result.error_message}")
            
            # 创建TableSchema对象
            return TableSchema(
                table_name=task.table_name,
                ddl_statement=task.ddl_statement,
                sample_data=sample_data.get('sample_data', []),
                column_count=len(sample_data.get('sample_data', [])),
                estimated_rows=sample_data.get('estimated_rows', 0)
            )
            
        except Exception as e:
            self.logger.error(f"推断表结构异常: {str(e)}")
            if task_id in self.tasks:
                self.tasks[task_id].status = "failed"
                self.tasks[task_id].error_message = str(e)
            
            if self.error_callback:
                self.error_callback(f"推断异常: {str(e)}")
            
            raise
    
    def wait_for_user_confirmation(self, schema: TableSchema) -> TableSchema:
        """
        等待用户确认（命令行模式）
        
        Args:
            schema: 表结构
            
        Returns:
            确认后的表结构
        """
        if not self.config.get('migration', {}).get('enable_user_confirmation', True):
            return schema
        
        print(f"\n=== 表结构推断完成 ===")
        print(f"表名: {schema.table_name}")
        print(f"DDL语句:")
        print("-" * 50)
        print(schema.ddl_statement)
        print("-" * 50)
        
        while True:
            choice = input("\n请选择操作: (c)确认 (m)修改 (s)跳过: ").lower().strip()
            
            if choice == 'c':
                self.logger.info(f"用户确认DDL: {schema.table_name}")
                break
            elif choice == 'm':
                print("请输入修改后的DDL语句 (输入END结束):")
                ddl_lines = []
                while True:
                    line = input()
                    if line.strip() == 'END':
                        break
                    ddl_lines.append(line)
                
                new_ddl = '\n'.join(ddl_lines)
                if new_ddl.strip():
                    schema.ddl_statement = new_ddl
                    self.logger.info(f"用户修改DDL: {schema.table_name}")
                    break
            elif choice == 's':
                self.logger.info(f"用户跳过表: {schema.table_name}")
                return None
            else:
                print("无效选择，请重新输入")
        
        # 更新任务状态
        if self.active_task:
            self.active_task.ddl_statement = schema.ddl_statement
            self.active_task.status = "confirmed"
        
        return schema
    
    def create_table(self, schema: TableSchema) -> bool:
        """
        创建表
        
        Args:
            schema: 表结构
            
        Returns:
            是否成功
        """
        try:
            self._update_progress(f"正在创建表: {schema.table_name}")
            
            # 检查表是否已存在
            if self.db_connection.check_table_exists(schema.table_name):
                choice = input(f"表 {schema.table_name} 已存在，是否删除重建? (y/n): ")
                if choice.lower() == 'y':
                    drop_result = self.db_connection.drop_table(schema.table_name)
                    if not drop_result.success:
                        raise Exception(f"删除表失败: {drop_result.error_message}")
                else:
                    self.logger.info(f"跳过已存在的表: {schema.table_name}")
                    return True
            
            # 创建表
            result = self.db_connection.create_table(schema.ddl_statement)
            
            if result.success:
                self.logger.info(f"表创建成功: {schema.table_name}")
                if self.active_task:
                    self.active_task.status = "importing"
                return True
            else:
                error_msg = f"创建表失败: {result.error_message}"
                self.logger.error(error_msg)
                if self.active_task:
                    self.active_task.status = "failed"
                    self.active_task.error_message = error_msg
                if self.error_callback:
                    self.error_callback(error_msg)
                return False
                
        except Exception as e:
            error_msg = f"创建表异常: {str(e)}"
            self.logger.error(error_msg)
            if self.active_task:
                self.active_task.status = "failed"
                self.active_task.error_message = error_msg
            if self.error_callback:
                self.error_callback(error_msg)
            return False
    
    def import_data_parallel(self, sql_file: str) -> ImportResult:
        """
        并行导入数据
        
        Args:
            sql_file: SQL文件路径
            
        Returns:
            导入结果
        """
        try:
            table_name = self.active_task.table_name if self.active_task else "unknown_table"
            
            self._update_progress(f"开始并行导入数据: {table_name}")
            
            # 创建并行导入器
            importer = ParallelImporter(self.config, self._progress_callback_wrapper)
            
            # 执行导入
            result = importer.import_data_with_retry(table_name, sql_file)
            
            # 更新任务状态
            if self.active_task:
                self.active_task.import_result = result
                self.active_task.status = "completed" if result.success else "failed"
                self.active_task.completed_at = time.time()
                if not result.success:
                    self.active_task.error_message = "; ".join(result.error_messages)
            
            if result.success:
                self.logger.info(f"数据导入成功: {table_name}, 导入行数: {result.total_rows_imported}")
                if self.completion_callback:
                    self.completion_callback(result)
            else:
                self.logger.error(f"数据导入失败: {table_name}")
                if self.error_callback:
                    self.error_callback(f"导入失败: {'; '.join(result.error_messages)}")
            
            return result
            
        except Exception as e:
            error_msg = f"导入数据异常: {str(e)}"
            self.logger.error(error_msg)
            
            if self.active_task:
                self.active_task.status = "failed"
                self.active_task.error_message = error_msg
                self.active_task.completed_at = time.time()
            
            if self.error_callback:
                self.error_callback(error_msg)
            
            # 返回失败结果
            return ImportResult(
                task_id=self.active_task.task_id if self.active_task else "unknown",
                table_name=self.active_task.table_name if self.active_task else "unknown",
                total_tasks=0,
                completed_tasks=0,
                failed_tasks=1,
                total_rows_imported=0,
                total_execution_time=0,
                success=False,
                error_messages=[str(e)]
            )
    
    def migrate_single_table(self, sql_file: str, auto_confirm: bool = False) -> bool:
        """
        迁移单个表（完整流程）
        
        Args:
            sql_file: SQL文件路径
            auto_confirm: 是否自动确认DDL
            
        Returns:
            是否成功
        """
        try:
            self.logger.info(f"开始迁移表: {sql_file}")
            
            # 1. 推断表结构
            schema = self.infer_schema(sql_file)
            
            if not schema or not schema.ddl_statement:
                self.logger.error("表结构推断失败")
                return False
            
            # 2. 用户确认（如果启用）
            if not auto_confirm:
                confirmed_schema = self.wait_for_user_confirmation(schema)
                if not confirmed_schema:
                    self.logger.info("用户跳过此表")
                    return True
                schema = confirmed_schema
            
            # 3. 创建表
            if not self.create_table(schema):
                return False
            
            # 4. 导入数据
            result = self.import_data_parallel(sql_file)
            
            return result.success
            
        except Exception as e:
            self.logger.error(f"迁移表失败: {str(e)}")
            return False
    
    def migrate_multiple_tables(self, sql_files: List[str], auto_confirm: bool = False) -> Dict[str, bool]:
        """
        迁移多个表
        
        Args:
            sql_files: SQL文件路径列表
            auto_confirm: 是否自动确认DDL
            
        Returns:
            每个文件的迁移结果
        """
        results = {}
        
        self.logger.info(f"开始批量迁移 {len(sql_files)} 个表")
        
        for i, sql_file in enumerate(sql_files, 1):
            self.logger.info(f"处理第 {i}/{len(sql_files)} 个文件: {sql_file}")
            
            try:
                success = self.migrate_single_table(sql_file, auto_confirm)
                results[sql_file] = success
                
                if success:
                    self.logger.info(f"文件迁移成功: {sql_file}")
                else:
                    self.logger.error(f"文件迁移失败: {sql_file}")
                    
            except Exception as e:
                self.logger.error(f"处理文件异常: {sql_file}, 错误: {str(e)}")
                results[sql_file] = False
        
        # 汇总结果
        success_count = sum(1 for success in results.values() if success)
        total_count = len(sql_files)
        
        self.logger.info(f"批量迁移完成: 成功 {success_count}/{total_count} 个表")
        
        return results
    
    def get_task_status(self, task_id: str) -> Optional[MigrationTask]:
        """获取任务状态"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[MigrationTask]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def _update_progress(self, message: str):
        """更新进度"""
        self.logger.info(message)
        if self.progress_callback:
            self.progress_callback(message)
    
    def _progress_callback_wrapper(self, progress_data: Dict):
        """进度回调包装器"""
        if self.progress_callback:
            self.progress_callback(progress_data)
    
    def cleanup(self):
        """清理资源"""
        # 清理临时文件等
        if hasattr(self, 'temp_dir'):
            import shutil
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except:
                pass
        
        self.logger.info("迁移器清理完成")
    
    # ======== 服务器文件路径处理功能 ========
    
    def validate_server_file_path(self, file_path: str) -> Dict:
        """
        验证服务器文件路径
        
        Args:
            file_path: 文件路径
            
        Returns:
            验证结果字典 {'success': bool, 'message': str, 'error_code': str}
        """
        try:
            # 获取文件访问配置
            file_access_config = self.config.get('file_access', {})
            
            # 检查是否启用服务器路径功能
            if not file_access_config.get('enable_server_path_input', False):
                return {
                    'success': False,
                    'message': '服务器文件路径功能未启用',
                    'error_code': 'FEATURE_DISABLED'
                }
            
            # 路径格式检查
            if not file_path or not isinstance(file_path, str):
                return {
                    'success': False,
                    'message': '文件路径不能为空',
                    'error_code': 'PATH_001'
                }
            
            # 路径长度检查
            max_path_length = file_access_config.get('max_path_length', 255)
            if len(file_path) > max_path_length:
                return {
                    'success': False,
                    'message': f'文件路径长度超过限制（{max_path_length}字符）',
                    'error_code': 'PATH_001'
                }
            
            # 规范化路径
            normalized_path = self._normalize_file_path(file_path)
            
            # 安全性检查
            security_result = self._is_path_safe(normalized_path)
            if not security_result['safe']:
                return {
                    'success': False,
                    'message': security_result['message'],
                    'error_code': 'PATH_002'
                }
            
            # 文件存在检查
            if not os.path.exists(normalized_path):
                return {
                    'success': False,
                    'message': '文件不存在',
                    'error_code': 'PATH_003'
                }
            
            # 是否为文件（非目录）
            if not os.path.isfile(normalized_path):
                return {
                    'success': False,
                    'message': '指定路径不是文件',
                    'error_code': 'PATH_003'
                }
            
            # 权限检查
            if not os.access(normalized_path, os.R_OK):
                return {
                    'success': False,
                    'message': '文件无法读取',
                    'error_code': 'PATH_004'
                }
            
            # 文件扩展名检查
            allowed_extensions = file_access_config.get('allowed_extensions', ['.sql'])
            file_ext = os.path.splitext(normalized_path)[1].lower()
            if file_ext not in allowed_extensions:
                return {
                    'success': False,
                    'message': f'不支持的文件类型，仅支持: {", ".join(allowed_extensions)}',
                    'error_code': 'PATH_001'
                }
            
            # 文件大小检查
            max_size_mb = file_access_config.get('max_file_size_mb', 2048)
            file_size_mb = os.path.getsize(normalized_path) / (1024 * 1024)
            if file_size_mb > max_size_mb:
                return {
                    'success': False,
                    'message': f'文件大小超过限制（{max_size_mb}MB）',
                    'error_code': 'PATH_005'
                }
            
            return {
                'success': True,
                'message': '文件路径验证成功',
                'normalized_path': normalized_path
            }
            
        except Exception as e:
            self.logger.error(f"验证服务器文件路径异常: {str(e)}")
            return {
                'success': False,
                'message': f'验证异常: {str(e)}',
                'error_code': 'SYSTEM_ERROR'
            }
    
    def get_server_file_info(self, file_path: str) -> Dict:
        """
        获取服务器文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息字典
        """
        try:
            # 先验证路径
            validation_result = self.validate_server_file_path(file_path)
            if not validation_result['success']:
                return validation_result
            
            normalized_path = validation_result['normalized_path']
            
            # 获取文件统计信息
            stat = os.stat(normalized_path)
            file_size = stat.st_size
            
            # 估算行数（快速采样）
            estimated_rows = self._estimate_file_lines(normalized_path)
            
            # 获取文件基本信息
            file_info = {
                'success': True,
                'file_path': normalized_path,
                'filename': os.path.basename(normalized_path),
                'file_size': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'estimated_rows': estimated_rows,
                'last_modified': stat.st_mtime,
                'readable': os.access(normalized_path, os.R_OK),
                'file_extension': os.path.splitext(normalized_path)[1]
            }
            
            return file_info
            
        except Exception as e:
            self.logger.error(f"获取服务器文件信息异常: {str(e)}")
            return {
                'success': False,
                'message': f'获取文件信息异常: {str(e)}',
                'error_code': 'SYSTEM_ERROR'
            }
    
    def process_server_file(self, file_path: str, task_id: Optional[str] = None) -> Dict:
        """
        处理服务器文件（启动完整迁移流程）
        
        Args:
            file_path: 文件路径
            task_id: 任务ID（可选）
            
        Returns:
            处理结果
        """
        try:
            # 先验证路径
            validation_result = self.validate_server_file_path(file_path)
            if not validation_result['success']:
                return validation_result
            
            normalized_path = validation_result['normalized_path']
            
            # 生成任务ID
            if task_id is None:
                task_id = f"server_task_{int(time.time())}"
            
            # 创建任务
            task = MigrationTask(
                task_id=task_id,
                sql_file=normalized_path,
                table_name="",
                status="parsing",
                created_at=time.time()
            )
            self.tasks[task_id] = task
            self.active_task = task
            
            self.logger.info(f"开始处理服务器文件: {normalized_path}")
            
            # 解析SQL文件（使用现有逻辑）
            self._update_progress("正在解析SQL文件...")
            sample_data = self.sql_parser.extract_sample_data(normalized_path)
            task.sample_data = sample_data
            task.table_name = sample_data.get('table_name', 'unknown_table')
            task.status = "inferring"
            
            self.logger.info(f"服务器文件解析完成，表名: {task.table_name}")
            
            # AI推断表结构
            self._update_progress("正在推断表结构...")
            inference_result = self.schema_engine.infer_table_schema(sample_data)
            task.inference_result = inference_result
            task.ddl_statement = inference_result.ddl_statement
            
            if inference_result.success:
                task.status = "waiting_confirm"
                self.logger.info(f"服务器文件表结构推断成功: {task.table_name}")
                
                return {
                    'success': True,
                    'task_id': task_id,
                    'table_name': task.table_name,
                    'ddl_statement': task.ddl_statement,
                    'confidence_score': inference_result.confidence_score,
                    'message': '表结构推断完成，等待用户确认...'
                }
            else:
                task.status = "failed"
                task.error_message = inference_result.error_message
                self.logger.error(f"服务器文件表结构推断失败: {inference_result.error_message}")
                
                return {
                    'success': False,
                    'task_id': task_id,
                    'message': f'推断失败: {inference_result.error_message}',
                    'error_code': 'INFERENCE_FAILED'
                }
            
        except Exception as e:
            self.logger.error(f"处理服务器文件异常: {str(e)}")
            if task_id and task_id in self.tasks:
                self.tasks[task_id].status = "failed"
                self.tasks[task_id].error_message = str(e)
            
            return {
                'success': False,
                'message': f'处理异常: {str(e)}',
                'error_code': 'SYSTEM_ERROR'
            }
    
    def _normalize_file_path(self, file_path: str) -> str:
        """
        规范化文件路径
        
        Args:
            file_path: 原始文件路径
            
        Returns:
            规范化后的路径
        """
        # 规范化路径，解决相对路径和路径遍历问题
        normalized = os.path.normpath(os.path.abspath(file_path))
        return normalized
    
    def _is_path_safe(self, file_path: str) -> Dict:
        """
        检查路径安全性
        
        Args:
            file_path: 文件路径
            
        Returns:
            安全检查结果 {'safe': bool, 'message': str}
        """
        try:
            file_access_config = self.config.get('file_access', {})
            
            # 如果禁用路径遍历保护，直接返回安全
            if not file_access_config.get('enable_path_traversal_protection', True):
                return {'safe': True, 'message': '路径安全检查已禁用'}
            
            # 获取允许访问的目录列表
            allowed_directories = file_access_config.get('allowed_directories', [])
            
            if not allowed_directories:
                return {'safe': True, 'message': '未配置允许目录白名单'}
            
            # 检查文件是否在允许的目录中
            file_path_abs = os.path.abspath(file_path)
            
            for allowed_dir in allowed_directories:
                allowed_dir_abs = os.path.abspath(allowed_dir)
                
                # 检查文件是否在允许的目录或其子目录中
                try:
                    os.path.commonpath([file_path_abs, allowed_dir_abs])
                    if file_path_abs.startswith(allowed_dir_abs + os.sep) or file_path_abs == allowed_dir_abs:
                        return {'safe': True, 'message': '路径安全检查通过'}
                except ValueError:
                    # 不同驱动器的路径会抛出ValueError
                    continue
            
            return {
                'safe': False,
                'message': f'文件路径不在允许访问的目录中: {", ".join(allowed_directories)}'
            }
            
        except Exception as e:
            self.logger.error(f"路径安全检查异常: {str(e)}")
            return {
                'safe': False,
                'message': f'安全检查异常: {str(e)}'
            }
    
    def _estimate_file_lines(self, file_path: str, sample_size: int = 8192) -> int:
        """
        估算文件行数
        
        Args:
            file_path: 文件路径
            sample_size: 采样大小（字节）
            
        Returns:
            估算的行数
        """
        try:
            file_size = os.path.getsize(file_path)
            
            if file_size == 0:
                return 0
            
            # 如果文件很小，直接计算行数
            if file_size <= sample_size:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return sum(1 for _ in f)
            
            # 采样计算平均行长度
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                sample_data = f.read(sample_size)
                sample_lines = sample_data.count('\n')
                
                if sample_lines == 0:
                    return 1  # 至少有一行
                
                # 估算总行数
                avg_line_length = len(sample_data) / sample_lines
                estimated_lines = int(file_size / avg_line_length)
                
                return max(1, estimated_lines)
                
        except Exception as e:
            self.logger.warning(f"估算文件行数失败: {str(e)}")
            return 0