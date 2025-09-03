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
        
        # 获取通信配置
        self.comm_config = self.config.get('web_interface', {}).get('communication', {})
        self.comm_mode = self.comm_config.get('mode', 'auto')
        self.polling_interval = self.comm_config.get('polling_interval', 2)
        self.websocket_timeout = self.comm_config.get('websocket_timeout', 120)
        self.fallback_to_polling = self.comm_config.get('fallback_to_polling', True)
        
        # 初始化Flask应用
        self.app = Flask(__name__, 
                         template_folder='../templates',
                         static_folder='../static')
        self.app.config['SECRET_KEY'] = self.config.get('web_interface', {}).get('secret_key', 'dev_secret_key')
        
        # 根据配置初始化SocketIO
        self.socketio = self._init_socketio()
        
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
    
    def _init_socketio(self):
        """根据配置初始化SocketIO"""
        if self.comm_mode == 'polling_only':
            # 仅使用轮询模式
            socketio_config = {
                'cors_allowed_origins': "*",
                'transports': ['polling'],
                'ping_timeout': self.websocket_timeout,
                'ping_interval': self.polling_interval
            }
            self.logger.info("使用纯轮询模式")
        elif self.comm_mode == 'polling':
            # 轮询优先模式
            socketio_config = {
                'cors_allowed_origins': "*",
                'transports': ['polling', 'websocket'],
                'ping_timeout': self.websocket_timeout,
                'ping_interval': self.polling_interval
            }
            self.logger.info("使用轮询优先模式")
        elif self.comm_mode == 'websocket':
            # WebSocket优先模式
            socketio_config = {
                'cors_allowed_origins': "*",
                'transports': ['websocket', 'polling'] if self.fallback_to_polling else ['websocket'],
                'ping_timeout': self.websocket_timeout,
                'ping_interval': self.comm_config.get('heartbeat_interval', 20)
            }
            self.logger.info(f"WebSocket优先模式，回退: {self.fallback_to_polling}")
        else:
            # 自动模式（默认）
            socketio_config = {
                'cors_allowed_origins': "*",
                'transports': ['polling', 'websocket'],
                'ping_timeout': self.websocket_timeout,
                'ping_interval': max(self.polling_interval, 5)  # 自动模式下保持合理间隔
            }
            self.logger.info("使用自动模式（轮询+WebSocket）")
        
        return SocketIO(self.app, **socketio_config)
    
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
                        'progress': task_info.get('progress', 0),
                        'ddl_statement': task_info.get('ddl_statement', ''),
                        'confidence_score': task_info.get('confidence_score', 0),
                        'estimated_rows': task_info.get('estimated_rows', 0),
                        'sample_data': task_info.get('sample_data', {}),
                        'created_at': task_info.get('created_at', 0),
                        'is_server_file': task_info.get('is_server_file', False)
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
        
        # ======== 轮询模式API ========
        
        @self.app.route('/poll/status')
        def poll_status():
            """轮询模式状态获取"""
            try:
                # 获取所有任务状态
                tasks_status = {
                    task_id: {
                        'status': task_info['status'],
                        'progress': task_info.get('progress', 0),
                        'table_name': task_info.get('table_name', ''),
                        'filename': task_info.get('filename', ''),
                        'ddl_statement': task_info.get('ddl_statement', ''),
                        'confidence_score': task_info.get('confidence_score', 0),
                        'estimated_rows': task_info.get('estimated_rows', 0),
                        'last_update': task_info.get('last_update', time.time()),
                        'error_message': task_info.get('error_message', '')
                    }
                    for task_id, task_info in self.active_tasks.items()
                }
                
                return jsonify({
                    'success': True,
                    'tasks': tasks_status,
                    'server_time': time.time(),
                    'communication_mode': self.comm_mode
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/poll/events/<task_id>')
        def poll_task_events(task_id):
            """轮询模式任务事件获取"""
            try:
                if task_id in self.active_tasks:
                    task_info = self.active_tasks[task_id]
                    
                    # 构建事件响应
                    events = []
                    
                    # 根据任务状态生成事件
                    if task_info['status'] == 'waiting_confirmation':
                        events.append({
                            'type': 'schema_inferred',
                            'data': {
                                'task_id': task_id,
                                'table_name': task_info.get('table_name', ''),
                                'ddl_statement': task_info.get('ddl_statement', ''),
                                'confidence_score': task_info.get('confidence_score', 0),
                                'message': '表结构推断完成，等待用户确认...'
                            }
                        })
                    elif task_info['status'] == 'importing':
                        events.append({
                            'type': 'import_progress',
                            'data': {
                                'task_id': task_id,
                                'progress': task_info.get('progress', 0),
                                'message': '正在导入数据...'
                            }
                        })
                    elif task_info['status'] == 'completed':
                        events.append({
                            'type': 'import_completed',
                            'data': {
                                'task_id': task_id,
                                'message': '数据导入完成'
                            }
                        })
                    elif task_info['status'] == 'failed':
                        events.append({
                            'type': 'task_failed',
                            'data': {
                                'task_id': task_id,
                                'error_message': task_info.get('error_message', '未知错误')
                            }
                        })
                    
                    return jsonify({
                        'success': True,
                        'events': events,
                        'task_status': task_info['status']
                    })
                else:
                    return jsonify({
                        'success': False, 
                        'message': '任务不存在'
                    }), 404
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/confirm_ddl', methods=['POST'])
        def confirm_ddl_http():
            """轮询模式下DDL确认"""
            try:
                data = request.get_json()
                task_id = data.get('task_id')
                ddl_statement = data.get('ddl_statement')
                
                if not task_id or not ddl_statement:
                    return jsonify({
                        'success': False,
                        'message': '缺少必要参数'
                    }), 400
                
                if task_id in self.active_tasks:
                    self.active_tasks[task_id]['ddl_statement'] = ddl_statement
                    self.active_tasks[task_id]['status'] = 'ddl_confirmed'
                    self.active_tasks[task_id]['last_update'] = time.time()
                    
                    # 启动建表和导入
                    threading.Thread(
                        target=self._start_table_creation_and_import,
                        args=(task_id,)
                    ).start()
                    
                    # 同时发送WebSocket事件（如果有连接）
                    self.socketio.emit('ddl_confirmed', {
                        'task_id': task_id,
                        'message': 'DDL已确认，开始创建表和导入数据...'
                    })
                    
                    return jsonify({
                        'success': True,
                        'message': 'DDL已确认，开始执行...'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': '任务不存在'
                    }), 404
                    
            except Exception as e:
                self.logger.error(f"轮询模式确认DDL失败: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'服务器错误: {str(e)}'
                }), 500
        
        # ======== 服务器文件路径功能API ========
        
        @self.app.route('/validate_path', methods=['POST'])
        def validate_path():
            """验证服务器文件路径"""
            try:
                data = request.get_json()
                if not data or 'file_path' not in data:
                    return jsonify({
                        'success': False, 
                        'message': '缺少file_path参数'
                    }), 400
                
                file_path = data['file_path']
                
                # 创建临时迁移器实例进行验证
                from main_controller import OracleDoriseMigrator
                migrator = OracleDoriseMigrator()
                
                result = migrator.validate_server_file_path(file_path)
                
                if result['success']:
                    return jsonify(result)
                else:
                    return jsonify(result), 400
                    
            except Exception as e:
                self.logger.error(f"验证服务器文件路径失败: {str(e)}")
                return jsonify({
                    'success': False, 
                    'message': f'验证失败: {str(e)}'
                }), 500
        
        @self.app.route('/file_info', methods=['POST'])
        def get_file_info():
            """获取服务器文件信息"""
            try:
                data = request.get_json()
                if not data or 'file_path' not in data:
                    return jsonify({
                        'success': False, 
                        'message': '缺少file_path参数'
                    }), 400
                
                file_path = data['file_path']
                
                # 创建临时迁移器实例获取文件信息
                from main_controller import OracleDoriseMigrator
                migrator = OracleDoriseMigrator()
                
                result = migrator.get_server_file_info(file_path)
                
                if result['success']:
                    return jsonify(result)
                else:
                    return jsonify(result), 400
                    
            except Exception as e:
                self.logger.error(f"获取服务器文件信息失败: {str(e)}")
                return jsonify({
                    'success': False, 
                    'message': f'获取文件信息失败: {str(e)}'
                }), 500
        
        @self.app.route('/process_server_file', methods=['POST'])
        def process_server_file():
            """处理服务器文件"""
            try:
                data = request.get_json()
                if not data or 'file_path' not in data:
                    return jsonify({
                        'success': False, 
                        'message': '缺少file_path参数'
                    }), 400
                
                file_path = data['file_path']
                
                # 生成任务ID
                task_id = str(uuid.uuid4())
                
                # 启动后台处理线程
                threading.Thread(
                    target=self._process_server_file,
                    args=(task_id, file_path)
                ).start()
                
                return jsonify({
                    'success': True, 
                    'task_id': task_id,
                    'file_path': file_path,
                    'message': '服务器文件处理已启动...'
                })
                    
            except Exception as e:
                self.logger.error(f"处理服务器文件失败: {str(e)}")
                return jsonify({
                    'success': False, 
                    'message': f'处理失败: {str(e)}'
                }), 500
    
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
        
        @self.socketio.on('heartbeat')
        def handle_heartbeat(data):
            """处理心跳信号"""
            client_timestamp = data.get('timestamp', 0)
            page_visible = data.get('page_visible', True)
            
            emit('heartbeat_response', {
                'timestamp': time.time(),
                'client_timestamp': client_timestamp,
                'server_id': request.sid,
                'latency': time.time() * 1000 - client_timestamp if client_timestamp else 0,
                'page_visible': page_visible
            })
            
            # 如果页面不可见，记录日志
            if not page_visible:
                self.logger.debug(f"客户端页面不可见: {request.sid}")
        
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
                    # 更新任务状态
                    self.active_tasks[task_id]['status'] = 'cancelled'
                    
                    # 尝试取消后端任务（如果正在运行）
                    try:
                        from main_controller import OracleDoriseMigrator
                        migrator = OracleDoriseMigrator()
                        migrator.cancel_task(task_id)
                    except Exception as e:
                        self.logger.warning(f"取消后端任务失败: {str(e)}")
                    
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
            def inference_progress_callback(progress_data):
                self.socketio.emit('inference_progress', {
                    'task_id': task_id,
                    'stage': progress_data.get('stage', 'inference'),
                    'message': progress_data.get('message', '正在推断...'),
                    'progress': progress_data.get('progress', 0),
                    'inference_stage': progress_data.get('stage', ''),
                    'table_name': table_name
                })
            
            inference_result = self.schema_engine.infer_table_schema(sample_data, inference_progress_callback)
            
            self.active_tasks[task_id].update({
                'inference_result': inference_result,
                'ddl_statement': inference_result.ddl_statement,
                'confidence_score': inference_result.confidence_score,
                'estimated_rows': sample_data.get('estimated_rows', 0),
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
            
            # 更新任务时间戳
            self.active_tasks[task_id]['last_update'] = time.time()
            
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
            
            create_result = self.db_connection.create_table(ddl_statement, drop_if_exists=True)
            
            if not create_result.success:
                raise Exception(f"创建表失败: {create_result.error_message}")
            
            task_info.update({
                'status': 'importing',
                'progress': 60,
                'last_update': time.time()
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
    
    def _process_server_file(self, task_id: str, file_path: str):
        """处理服务器文件"""
        try:
            # 创建临时迁移器实例
            from main_controller import OracleDoriseMigrator
            migrator = OracleDoriseMigrator()
            
            # 定义进度回调函数，将解析进度发送到前端
            def progress_callback(progress_data):
                self.socketio.emit('parsing_progress', {
                    'task_id': task_id,
                    'stage': progress_data.get('stage', 'parsing'),
                    'message': progress_data.get('message', ''),
                    'progress': progress_data.get('progress', 0),
                    'table_name': progress_data.get('table_name', ''),
                    'estimated_rows': progress_data.get('estimated_rows', 0),
                    'file_size_mb': progress_data.get('file_size_mb', 0)
                })
            
            # 使用主控制器处理服务器文件
            result = migrator.process_server_file(file_path, task_id, progress_callback=progress_callback)
            
            if result['success']:
                # 初始化任务状态
                self.active_tasks[task_id] = {
                    'task_id': task_id,
                    'filename': os.path.basename(file_path),
                    'file_path': file_path,
                    'table_name': result.get('table_name', ''),
                    'ddl_statement': result.get('ddl_statement', ''),
                    'confidence_score': result.get('confidence_score', 0),
                    'estimated_rows': result.get('estimated_rows', 0),
                    'status': 'waiting_confirmation',
                    'progress': 90,
                    'created_at': time.time(),
                    'is_server_file': True  # 标记为服务器文件
                }
                
                # 发送任务开始事件
                self.socketio.emit('task_started', {
                    'task_id': task_id,
                    'message': '开始处理服务器文件...'
                })
                
                # 发送解析完成事件
                self.socketio.emit('parsing_completed', {
                    'task_id': task_id,
                    'table_name': result.get('table_name', ''),
                    'message': '服务器文件解析完成，开始推断表结构...'
                })
                
                # 发送推断完成事件
                self.socketio.emit('schema_inferred', {
                    'task_id': task_id,
                    'table_name': result.get('table_name', ''),
                    'ddl_statement': result.get('ddl_statement', ''),
                    'confidence_score': result.get('confidence_score', 0),
                    'message': '表结构推断完成，等待用户确认...'
                })
                
            else:
                # 处理失败
                error_code = result.get('error_code', 'UNKNOWN_ERROR')
                if error_code == 'TASK_CANCELLED':
                    # 任务被取消
                    self.active_tasks[task_id] = {
                        'task_id': task_id,
                        'filename': os.path.basename(file_path),
                        'file_path': file_path,
                        'status': 'cancelled',
                        'error_message': result.get('message', '任务已被取消'),
                        'created_at': time.time(),
                        'is_server_file': True
                    }
                    
                    self.socketio.emit('task_cancelled', {
                        'task_id': task_id,
                        'message': '任务已被取消'
                    })
                else:
                    # 其他失败
                    self.active_tasks[task_id] = {
                        'task_id': task_id,
                        'filename': os.path.basename(file_path),
                        'file_path': file_path,
                        'status': 'failed',
                        'error_message': result.get('message', '未知错误'),
                        'created_at': time.time(),
                        'is_server_file': True
                    }
                    
                    # 发送失败事件
                    self.socketio.emit('task_failed', {
                        'task_id': task_id,
                        'error_message': result.get('message', '未知错误')
                    })
                
        except Exception as e:
            self.logger.error(f"处理服务器文件异常: {str(e)}")
            
            # 初始化失败任务状态
            self.active_tasks[task_id] = {
                'task_id': task_id,
                'filename': os.path.basename(file_path),
                'file_path': file_path,
                'status': 'failed',
                'error_message': str(e),
                'created_at': time.time(),
                'is_server_file': True
            }
            
            # 发送失败事件
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