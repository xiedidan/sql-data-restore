"""
Web界面后端应用

基于Flask和SocketIO实现实时Web界面
"""

import os
import logging
import uuid
import threading
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import yaml
from typing import Dict, List
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sql_parser import SQLFileParser
from core.schema_inference import SchemaInferenceEngine
from core.doris_connection import DorisConnection
from core.parallel_importer import ParallelImporter

class MigrationWebApp:
    """迁移Web应用"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化Web应用
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = self._load_config(config_path)
        
        # 初始化Flask应用
        self.app = Flask(__name__, 
                         template_folder='../../templates',
                         static_folder='../../static')
        self.app.config['SECRET_KEY'] = self.config.get('web_interface', {}).get('secret_key', 'dev_secret_key')
        
        # 初始化SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # 初始化核心组件
        self.sql_parser = SQLFileParser(self.config)
        self.schema_engine = SchemaInferenceEngine(self.config)
        self.db_connection = DorisConnection(self.config)
        
        # 任务管理
        self.active_tasks = {}
        self.upload_folder = './uploads'
        os.makedirs(self.upload_folder, exist_ok=True)
        
        # 设置日志
        self._setup_logging()
        
        # 注册路由和事件
        self._register_routes()
        self._register_socketio_events()
        
        self.logger = logging.getLogger(__name__)
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            # 返回默认配置
            return {
                'web_interface': {'host': '0.0.0.0', 'port': 5000, 'debug': False},
                'migration': {'sample_lines': 100, 'max_workers': 8}
            }
    
    def _setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('web_app.log', encoding='utf-8')
            ]
        )
    
    def _register_routes(self):
        """注册Flask路由"""
        
        @self.app.route('/')
        def index():
            """主页"""
            return render_template('index.html')
        
        @self.app.route('/upload', methods=['POST'])
        def upload_file():
            """文件上传"""
            try:
                if 'file' not in request.files:
                    return jsonify({'success': False, 'message': '没有文件'}), 400
                
                file = request.files['file']
                if file.filename == '':
                    return jsonify({'success': False, 'message': '没有选择文件'}), 400
                
                if file and file.filename.endswith('.sql'):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(self.upload_folder, filename)
                    file.save(file_path)
                    
                    # 生成任务ID
                    task_id = str(uuid.uuid4())
                    
                    # 启动后台处理
                    threading.Thread(
                        target=self._process_uploaded_file,
                        args=(task_id, file_path, filename)
                    ).start()
                    
                    return jsonify({
                        'success': True, 
                        'task_id': task_id,
                        'filename': filename,
                        'message': '文件上传成功，正在处理...'
                    })
                else:
                    return jsonify({'success': False, 'message': '请上传.sql文件'}), 400
                    
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)}), 500
        
        @self.app.route('/tasks')
        def get_tasks():
            """获取任务列表"""
            return jsonify({
                'tasks': [
                    {
                        'task_id': task_id,
                        'status': task_info['status'],
                        'table_name': task_info.get('table_name', ''),
                        'filename': task_info.get('filename', ''),
                        'progress': task_info.get('progress', 0)
                    }
                    for task_id, task_info in self.active_tasks.items()
                ]
            })
        
        @self.app.route('/task/<task_id>')
        def get_task_detail(task_id):
            """获取任务详情"""
            if task_id in self.active_tasks:
                return jsonify({
                    'success': True,
                    'task': self.active_tasks[task_id]
                })
            else:
                return jsonify({'success': False, 'message': '任务不存在'}), 404
    
    def _register_socketio_events(self):
        """注册SocketIO事件"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """客户端连接"""
            self.logger.info(f"客户端连接: {request.sid}")
            emit('connected', {'status': '连接成功'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客户端断开"""
            self.logger.info(f"客户端断开: {request.sid}")
        
        @self.socketio.on('confirm_ddl')
        def handle_confirm_ddl(data):
            """确认DDL语句"""
            try:
                task_id = data.get('task_id')
                ddl_statement = data.get('ddl_statement')
                
                if task_id in self.active_tasks:
                    self.active_tasks[task_id]['ddl_statement'] = ddl_statement
                    self.active_tasks[task_id]['status'] = 'ddl_confirmed'
                    
                    # 启动建表和导入
                    threading.Thread(
                        target=self._start_table_creation_and_import,
                        args=(task_id,)
                    ).start()
                    
                    emit('ddl_confirmed', {
                        'task_id': task_id,
                        'message': 'DDL已确认，开始创建表和导入数据...'
                    })
                else:
                    emit('error', {'message': '任务不存在'})
                    
            except Exception as e:
                self.logger.error(f"确认DDL失败: {str(e)}")
                emit('error', {'message': str(e)})
        
        @self.socketio.on('modify_ddl')
        def handle_modify_ddl(data):
            """修改DDL语句"""
            try:
                task_id = data.get('task_id')
                ddl_statement = data.get('ddl_statement')
                
                if task_id in self.active_tasks:
                    self.active_tasks[task_id]['ddl_statement'] = ddl_statement
                    emit('ddl_modified', {
                        'task_id': task_id,
                        'ddl_statement': ddl_statement,
                        'message': 'DDL已修改'
                    })
                else:
                    emit('error', {'message': '任务不存在'})
                    
            except Exception as e:
                self.logger.error(f"修改DDL失败: {str(e)}")
                emit('error', {'message': str(e)})
        
        @self.socketio.on('cancel_task')
        def handle_cancel_task(data):
            """取消任务"""
            try:
                task_id = data.get('task_id')
                
                if task_id in self.active_tasks:
                    self.active_tasks[task_id]['status'] = 'cancelled'
                    emit('task_cancelled', {
                        'task_id': task_id,
                        'message': '任务已取消'
                    })
                else:
                    emit('error', {'message': '任务不存在'})
                    
            except Exception as e:
                self.logger.error(f"取消任务失败: {str(e)}")
                emit('error', {'message': str(e)})
    
    def _process_uploaded_file(self, task_id: str, file_path: str, filename: str):
        """处理上传的文件"""
        try:
            # 初始化任务状态
            self.active_tasks[task_id] = {
                'task_id': task_id,
                'filename': filename,
                'file_path': file_path,
                'status': 'parsing',
                'progress': 0,
                'created_at': time.time()
            }
            
            # 发送开始解析事件
            self.socketio.emit('task_started', {
                'task_id': task_id,
                'message': '开始解析SQL文件...'
            })
            
            # 解析SQL文件
            sample_data = self.sql_parser.extract_sample_data(file_path)
            table_name = sample_data.get('table_name', 'unknown_table')
            
            self.active_tasks[task_id].update({
                'table_name': table_name,
                'sample_data': sample_data,
                'status': 'inferring',
                'progress': 20
            })
            
            # 发送解析完成事件
            self.socketio.emit('parsing_completed', {
                'task_id': task_id,
                'table_name': table_name,
                'sample_data': sample_data,
                'message': 'SQL文件解析完成，开始推断表结构...'
            })
            
            # AI推断表结构
            inference_result = self.schema_engine.infer_table_schema(sample_data)
            
            self.active_tasks[task_id].update({
                'inference_result': inference_result,
                'ddl_statement': inference_result.ddl_statement,
                'status': 'waiting_confirmation',
                'progress': 50
            })
            
            # 发送推断完成事件
            self.socketio.emit('schema_inferred', {
                'task_id': task_id,
                'table_name': table_name,
                'ddl_statement': inference_result.ddl_statement,
                'confidence_score': inference_result.confidence_score,
                'message': '表结构推断完成，等待用户确认...'
            })
            
        except Exception as e:
            self.logger.error(f"处理上传文件失败: {str(e)}")
            self.active_tasks[task_id].update({
                'status': 'failed',
                'error_message': str(e)
            })
            
            self.socketio.emit('task_failed', {
                'task_id': task_id,
                'error_message': str(e)
            })
    
    def _start_table_creation_and_import(self, task_id: str):
        """开始建表和导入数据"""
        try:
            task_info = self.active_tasks[task_id]
            ddl_statement = task_info['ddl_statement']
            table_name = task_info['table_name']
            file_path = task_info['file_path']
            
            # 创建表
            self.socketio.emit('table_creating', {
                'task_id': task_id,
                'message': '正在创建表...'
            })
            
            create_result = self.db_connection.create_table(ddl_statement)
            
            if not create_result.success:
                raise Exception(f"创建表失败: {create_result.error_message}")
            
            task_info.update({
                'status': 'importing',
                'progress': 60
            })
            
            self.socketio.emit('table_created', {
                'task_id': task_id,
                'message': '表创建成功，开始导入数据...'
            })
            
            # 并行导入数据
            def progress_callback(progress_data):
                """进度回调"""
                self.socketio.emit('import_progress', {
                    'task_id': task_id,
                    'progress_data': progress_data
                })
            
            importer = ParallelImporter(self.config, progress_callback)
            import_result = importer.import_data_with_retry(table_name, file_path)
            
            # 更新最终状态
            final_status = 'completed' if import_result.success else 'failed'
            task_info.update({
                'status': final_status,
                'progress': 100 if import_result.success else task_info.get('progress', 60),
                'import_result': import_result
            })
            
            # 发送完成事件
            self.socketio.emit('import_completed', {
                'task_id': task_id,
                'success': import_result.success,
                'table_name': table_name,
                'total_rows': import_result.total_rows_imported,
                'execution_time': import_result.total_execution_time,
                'message': '数据导入完成' if import_result.success else '数据导入失败'
            })
            
        except Exception as e:
            self.logger.error(f"建表和导入失败: {str(e)}")
            self.active_tasks[task_id].update({
                'status': 'failed',
                'error_message': str(e)
            })
            
            self.socketio.emit('task_failed', {
                'task_id': task_id,
                'error_message': str(e)
            })
    
    def run(self, host: str = None, port: int = None, debug: bool = None):
        """运行Web应用"""
        web_config = self.config.get('web_interface', {})
        
        host = host or web_config.get('host', '0.0.0.0')
        port = port or web_config.get('port', 5000)
        debug = debug if debug is not None else web_config.get('debug', False)
        
        self.logger.info(f"启动Web应用: http://{host}:{port}")
        
        self.socketio.run(
            self.app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True
        )