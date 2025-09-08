/**
 * Oracle到Doris迁移工具 - 前端JavaScript
 */

class MigrationApp {
    constructor() {
        this.socket = null;
        this.currentTask = null;
        this.tasks = new Map();
        this.communicationMode = 'auto';  // 默认模式
        this.pollingInterval = null;
        this.pollingEnabled = false;
        this.lastServerTime = 0;
        
        this.init();
    }
    
    init() {
        // 首先检测服务器通信模式
        this.detectCommunicationMode().then(() => {
            if (this.communicationMode === 'polling_only') {
                this.log('使用纯轮询模式', 'info');
                this.initPollingMode();
            } else {
                this.log(`使用${this.communicationMode}模式`, 'info');
                this.initSocketIO();
                // 如果是轮询优先或自动模式，同时启用轮询作为备用
                if (this.communicationMode === 'polling' || this.communicationMode === 'auto') {
                    this.enablePollingBackup();
                }
            }
            
            this.initEventListeners();
            this.initFileUpload();
            this.initServerPathFeature();
            this.loadTasks();
            
            this.log('系统初始化完成', 'info');
        });
    }
    
    // 检测服务器通信模式
    async detectCommunicationMode() {
        try {
            const response = await fetch('/poll/status');
            const data = await response.json();
            
            if (data.success) {
                this.communicationMode = data.communication_mode || 'auto';
                this.log(`检测到服务器通信模式: ${this.communicationMode}`, 'info');
            } else {
                this.communicationMode = 'auto';  // 默认模式
            }
        } catch (error) {
            console.warn('无法检测通信模式，使用默认模式', error);
            this.communicationMode = 'auto';
        }
    }
    
    // 初始化纯轮询模式
    initPollingMode() {
        this.pollingEnabled = true;
        this.log('启用纯轮询模式', 'info');
        
        // 立即开始轮询
        this.startPolling();
        
        // 更新连接状态
        this.updateConnectionStatus(true);
    }
    
    // 启用轮询备用机制
    enablePollingBackup() {
        this.log('启用轮询备用机制', 'info');
        
        // WebSocket连接失败时自动切换到轮询
        if (this.socket) {
            this.socket.on('disconnect', () => {
                if (!this.pollingEnabled) {
                    this.log('WebSocket断开，切换到轮询模式', 'warning');
                    this.startPolling();
                }
            });
            
            this.socket.on('connect', () => {
                if (this.pollingEnabled) {
                    this.log('WebSocket重新连接，停止轮询模式', 'info');
                    this.stopPolling();
                }
            });
        }
    }
    
    // 开始轮询
    startPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
        
        this.pollingEnabled = true;
        this.updateConnectionStatus(true);
        
        this.pollingInterval = setInterval(() => {
            this.pollServerStatus();
        }, 2000); // 每2秒轮询一次
        
        // 立即执行一次轮询
        this.pollServerStatus();
        
        this.log('轮询模式已启动', 'success');
    }
    
    // 停止轮询
    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
        
        this.pollingEnabled = false;
        this.log('轮询模式已停止', 'info');
    }
    
    // 轮询服务器状态
    async pollServerStatus() {
        try {
            const response = await fetch('/poll/status');
            const data = await response.json();
            
            if (data.success) {
                this.handlePollingResponse(data);
            } else {
                this.log(`轮询失败: ${data.error || '未知错误'}`, 'error');
            }
        } catch (error) {
            console.error('轮询请求失败:', error);
            this.updateConnectionStatus(false);
        }
    }
    
    // 处理轮询响应
    handlePollingResponse(data) {
        // 更新服务器时间
        this.lastServerTime = data.server_time;
        
        // 更新任务状态
        const serverTasks = data.tasks || {};
        const hasChanges = this.updateTasksFromPolling(serverTasks);
        
        // 如果有变化，更新UI
        if (hasChanges) {
            this.updateTaskList(Object.values(serverTasks));
            this.checkForStatusUpdates(serverTasks);
        }
        
        // 更新连接状态
        this.updateConnectionStatus(true);
    }
    
    // 更新任务状态（轮询模式）
    updateTasksFromPolling(serverTasks) {
        let hasChanges = false;
        
        // 检查新任务或状态变化
        for (const [taskId, serverTask] of Object.entries(serverTasks)) {
            const localTask = this.tasks.get(taskId);
            
            if (!localTask) {
                // 新任务
                this.tasks.set(taskId, {
                    task_id: taskId,
                    ...serverTask,
                    created_at: Date.now() / 1000
                });
                hasChanges = true;
                this.log(`发现新任务: ${serverTask.table_name || serverTask.filename}`, 'info');
            } else {
                // 检查状态变化
                if (localTask.status !== serverTask.status || 
                    localTask.progress !== serverTask.progress ||
                    localTask.ddl_statement !== serverTask.ddl_statement) {
                    
                    // 更新本地任务
                    Object.assign(localTask, serverTask);
                    hasChanges = true;
                    
                    this.log(`任务状态更新: ${localTask.table_name || localTask.filename} - ${serverTask.status}`, 'info');
                }
            }
        }
        
        return hasChanges;
    }
    
    // 检查状态更新（轮询模式）
    checkForStatusUpdates(serverTasks) {
        for (const [taskId, serverTask] of Object.entries(serverTasks)) {
            if (serverTask.status === 'waiting_confirmation' && serverTask.ddl_statement) {
                // 检查是否需要显示DDL确认界面
                if (!this.currentTask || this.currentTask.task_id !== taskId) {
                    this.selectTask(taskId);
                    this.showDDLEditor();
                    this.log(`自动选择待确认任务: ${serverTask.table_name || serverTask.filename}`, 'success');
                    
                    // 滚动到DDL区域
                    document.getElementById('ddl-section').scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        }
    }
    
    // SocketIO初始化
    initSocketIO() {
        // 配置SocketIO选项
        const socketOptions = {
            transports: ['polling', 'websocket'],  // 允许多种传输方式
            upgrade: true,                         // 允许升级到WebSocket
            timeout: 120000,                      // 连接超时：120秒（延长以适应AI推断）
            forceNew: false,                      // 不强制创建新连接，允许复用
            reconnection: true,                   // 允许自动重连
            reconnectionDelay: 1000,              // 重连延迟：1秒
            reconnectionDelayMax: 10000,          // 最大重连延迟：10秒
            maxReconnectionAttempts: 15,          // 最大重连次数：增加到15次
            randomizationFactor: 0.3              // 重连随机化因子
        };
        
        this.socket = io(socketOptions);
        
        // 心跳保持 - 更频繁的心跳
        this.heartbeatInterval = setInterval(() => {
            if (this.socket && this.socket.connected) {
                this.socket.emit('heartbeat', {
                    timestamp: Date.now(),
                    client_id: this.socket.id,
                    page_visible: !document.hidden  // 页面可见性状态
                });
            }
        }, 20000);  // 每20秒发送一次心跳（更频繁）
        
        // 页面可见性变化时重新建立连接
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.socket && !this.socket.connected) {
                this.log('页面重新可见，尝试重新连接...', 'info');
                this.socket.connect();
            }
        });
        
        this.socket.on('connect', () => {
            this.updateConnectionStatus(true);
            this.log('连接到服务器成功', 'success');
            
            // 连接成功后立即加载任务
            this.loadTasks();
        });
        
        this.socket.on('disconnect', (reason) => {
            this.updateConnectionStatus(false);
            this.log(`服务器连接断开: ${reason}`, 'warning');
            
            // 如果是意外断开，立即尝试重连
            if (reason === 'io server disconnect' || reason === 'ping timeout') {
                this.log('检测到意外断开，正在重连...', 'info');
                setTimeout(() => {
                    if (!this.socket.connected) {
                        this.socket.connect();
                    }
                }, 1000);
            }
        });
        
        this.socket.on('reconnect', (attemptNumber) => {
            this.updateConnectionStatus(true);
            this.log(`重新连接成功 (第${attemptNumber}次尝试)`, 'success');
            
            // 重连后立即加载任务并检查当前状态
            this.loadTasks(() => {
                // 检查是否有推断完成但界面未显示的任务
                this.checkPendingConfirmations();
            });
        });
        
        this.socket.on('reconnect_attempt', (attemptNumber) => {
            this.log(`正在尝试重新连接... (第${attemptNumber}次)`, 'info');
        });
        
        this.socket.on('reconnect_error', (error) => {
            this.log(`重连失败: ${error.toString()}`, 'error');
        });
        
        this.socket.on('connect_error', (error) => {
            this.log(`连接错误: ${error.toString()}`, 'error');
        });
        
        this.socket.on('heartbeat_response', (data) => {
            // 心跳响应，用于检查连接状态
            console.log('Heartbeat response:', data);
        });
        
        this.socket.on('task_started', (data) => {
            this.handleTaskStarted(data);
        });
        
        this.socket.on('parsing_completed', (data) => {
            this.handleParsingCompleted(data);
        });
        
        this.socket.on('schema_inferred', (data) => {
            this.handleSchemaInferred(data);
        });
        
        this.socket.on('ddl_confirmed', (data) => {
            this.handleDDLConfirmed(data);
        });
        
        this.socket.on('table_created', (data) => {
            this.handleTableCreated(data);
        });
        
        this.socket.on('import_progress', (data) => {
            this.handleImportProgress(data);
        });
        
        this.socket.on('import_completed', (data) => {
            this.handleImportCompleted(data);
        });
        
        this.socket.on('task_failed', (data) => {
            this.handleTaskFailed(data);
        });
        
        this.socket.on('parsing_progress', (data) => {
            this.handleParsingProgress(data);
        });
        
        this.socket.on('inference_progress', (data) => {
            this.handleInferenceProgress(data);
        });
        
        this.socket.on('task_cancelled', (data) => {
            this.handleTaskCancelled(data);
        });
        
        this.socket.on('error', (data) => {
            this.showModal('错误', data.message, 'error');
            this.log(`错误: ${data.message}`, 'error');
        });
    }
    
    // 事件监听器
    initEventListeners() {
        // 数据库选择
        document.querySelectorAll('input[name="target-database"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.handleDatabaseSelection(e.target.value);
            });
        });
        
        // DDL操作按钮
        document.getElementById('validate-ddl').addEventListener('click', () => {
            this.validateDDL();
        });
        
        document.getElementById('confirm-ddl').addEventListener('click', () => {
            this.confirmDDL();
        });
        
        document.getElementById('modify-ddl').addEventListener('click', () => {
            this.modifyDDL();
        });
        
        // 取消导入
        document.getElementById('cancel-import').addEventListener('click', () => {
            this.cancelImport();
        });
        
        // 清空日志
        document.getElementById('clear-logs').addEventListener('click', () => {
            this.clearLogs();
        });
        
        // ======== 服务器文件路径功能事件 ========
        
        // 路径验证按钮
        document.getElementById('validate-path-btn').addEventListener('click', () => {
            this.validateServerPath();
        });
        
        // 处理服务器文件按钮
        document.getElementById('process-server-file-btn').addEventListener('click', () => {
            this.processServerFile();
        });
        
        // 路径输入框回车键事件
        document.getElementById('server-path-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.validateServerPath();
            }
        });
        
        // 路径建议按钮事件
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('path-suggestion-btn')) {
                const path = e.target.getAttribute('data-path');
                document.getElementById('server-path-input').value = path;
            }
        });
    }
    
    // 文件上传初始化
    initFileUpload() {
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('file-input');
        
        // 拖拽上传
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].name.endsWith('.sql')) {
                this.uploadFile(files[0]);
            } else {
                this.showModal('文件类型错误', '请上传.sql文件', 'warning');
            }
        });
        
        // 点击上传
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.uploadFile(e.target.files[0]);
            }
        });
    }
    
    // 上传文件
    uploadFile(file) {
        if (!file.name.endsWith('.sql')) {
            this.showModal('文件类型错误', '请上传.sql文件', 'warning');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('target_database', this.getSelectedDatabase());
        
        this.log(`开始上传文件: ${file.name}`, 'info');
        
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.log(`文件上传成功: ${data.filename}`, 'success');
                // 任务会通过SocketIO事件更新
            } else {
                this.showModal('上传失败', data.message, 'error');
                this.log(`文件上传失败: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            this.showModal('上传错误', '网络错误，请重试', 'error');
            this.log(`文件上传错误: ${error.message}`, 'error');
        });
    }
    
    // ======== 服务器文件路径功能 ========
    
    // 初始化服务器路径功能
    initServerPathFeature() {
        this.currentValidatedFile = null;
        
        // 输入方式切换
        const inputModeRadios = document.querySelectorAll('input[name="input-mode"]');
        inputModeRadios.forEach(radio => {
            radio.addEventListener('change', () => {
                this.switchInputMode(radio.value);
            });
        });
        
        // 默认显示文件上传模式
        this.switchInputMode('upload');
    }
    
    // 切换输入模式
    switchInputMode(mode) {
        const uploadArea = document.getElementById('upload-area');
        const serverPathArea = document.getElementById('server-path-area');
        const fileInfoDisplay = document.getElementById('file-info-display');
        
        if (mode === 'upload') {
            uploadArea.style.display = 'block';
            serverPathArea.style.display = 'none';
            fileInfoDisplay.style.display = 'none';
        } else if (mode === 'server-path') {
            uploadArea.style.display = 'none';
            serverPathArea.style.display = 'block';
            // 保持文件信息显示状态
        }
        
        // 清空已验证的文件信息
        this.currentValidatedFile = null;
        
        this.log(`切换到${mode === 'upload' ? '文件上传' : '服务器路径'}模式`, 'info');
    }
    
    // 验证服务器文件路径
    async validateServerPath() {
        const pathInput = document.getElementById('server-path-input');
        const validateBtn = document.getElementById('validate-path-btn');
        const fileInfoDisplay = document.getElementById('file-info-display');
        
        const filePath = pathInput.value.trim();
        
        if (!filePath) {
            this.showModal('路径验证', '请输入文件路径', 'warning');
            return;
        }
        
        // 显示加载状态
        validateBtn.classList.add('loading');
        validateBtn.disabled = true;
        
        try {
            this.log(`正在验证路径: ${filePath}`, 'info');
            
            // 发送验证请求
            const response = await fetch('/validate_path', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ file_path: filePath })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.log('路径验证成功', 'success');
                
                // 获取文件信息
                await this.getServerFileInfo(filePath);
                
            } else {
                this.showModal('路径验证失败', result.message, 'error');
                this.log(`路径验证失败: ${result.message}`, 'error');
                fileInfoDisplay.style.display = 'none';
                this.currentValidatedFile = null;
            }
            
        } catch (error) {
            this.showModal('验证错误', '网络错误，请重试', 'error');
            this.log(`路径验证错误: ${error.message}`, 'error');
            fileInfoDisplay.style.display = 'none';
            this.currentValidatedFile = null;
            
        } finally {
            // 隐藏加载状态
            validateBtn.classList.remove('loading');
            validateBtn.disabled = false;
        }
    }
    
    // 获取服务器文件信息
    async getServerFileInfo(filePath) {
        try {
            const response = await fetch('/file_info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ file_path: filePath })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.displayFileInfo(result);
                this.currentValidatedFile = result;
                this.log('文件信息获取成功', 'success');
                
            } else {
                this.showModal('获取文件信息失败', result.message, 'error');
                this.log(`获取文件信息失败: ${result.message}`, 'error');
            }
            
        } catch (error) {
            this.showModal('获取信息错误', '网络错误，请重试', 'error');
            this.log(`获取文件信息错误: ${error.message}`, 'error');
        }
    }
    
    // 显示文件信息
    displayFileInfo(fileInfo) {
        const fileInfoDisplay = document.getElementById('file-info-display');
        
        document.getElementById('file-info-name').textContent = fileInfo.filename;
        document.getElementById('file-info-size').textContent = `${fileInfo.file_size_mb} MB`;
        document.getElementById('file-info-rows').textContent = fileInfo.estimated_rows.toLocaleString();
        document.getElementById('file-info-path').textContent = fileInfo.file_path;
        
        fileInfoDisplay.style.display = 'block';
    }
    
    // 处理服务器文件
    async processServerFile() {
        if (!this.currentValidatedFile) {
            this.showModal('无效操作', '请先验证文件路径', 'warning');
            return;
        }
        
        const processBtn = document.getElementById('process-server-file-btn');
        
        // 显示加载状态
        processBtn.classList.add('loading');
        processBtn.disabled = true;
        
        try {
            this.log(`开始处理服务器文件: ${this.currentValidatedFile.filename}`, 'info');
            
            const response = await fetch('/process_server_file', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    file_path: this.currentValidatedFile.file_path,
                    target_database: this.getSelectedDatabase()
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.log(`服务器文件处理已启动: ${result.task_id}`, 'success');
                
                // 隐藏文件信息显示，任务将通过SocketIO事件更新
                document.getElementById('file-info-display').style.display = 'none';
                
                // 清空输入框
                document.getElementById('server-path-input').value = '';
                this.currentValidatedFile = null;
                
            } else {
                this.showModal('处理失败', result.message, 'error');
                this.log(`服务器文件处理失败: ${result.message}`, 'error');
            }
            
        } catch (error) {
            this.showModal('处理错误', '网络错误，请重试', 'error');
            this.log(`服务器文件处理错误: ${error.message}`, 'error');
            
        } finally {
            // 隐藏加载状态
            processBtn.classList.remove('loading');
            processBtn.disabled = false;
        }
    }
    
    // 加载任务列表
    loadTasks(callback) {
        fetch('/tasks')
        .then(response => response.json())
        .then(data => {
            this.updateTaskList(data.tasks);
            if (callback) {
                callback(data.tasks);
            }
        })
        .catch(error => {
            this.log(`加载任务列表失败: ${error.message}`, 'error');
        });
    }
    
    // 更新连接状态
    updateConnectionStatus(connected) {
        const indicator = document.getElementById('connection-indicator');
        if (connected) {
            indicator.className = 'status-indicator online';
            indicator.innerHTML = '<i class="fas fa-circle"></i> 在线';
        } else {
            indicator.className = 'status-indicator offline';
            indicator.innerHTML = '<i class="fas fa-circle"></i> 离线';
        }
    }
    
    // 更新任务列表
    updateTaskList(tasks) {
        const taskList = document.getElementById('task-list');
        
        if (tasks.length === 0) {
            taskList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>暂无任务</p>
                </div>
            `;
            return;
        }
        
        taskList.innerHTML = tasks.map(task => `
            <div class="task-item ${task.task_id === this.currentTask?.task_id ? 'active' : ''}" 
                 onclick="app.selectTask('${task.task_id}')">
                <div class="task-title">${task.table_name || task.filename}</div>
                <div class="task-status">${this.getStatusText(task.status)}</div>
                ${task.progress > 0 ? `
                    <div class="task-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${task.progress}%"></div>
                        </div>
                    </div>
                ` : ''}
            </div>
        `).join('');
        
        // 更新任务映射
        tasks.forEach(task => {
            this.tasks.set(task.task_id, task);
        });
    }
    
    // 选择任务
    selectTask(taskId) {
        const task = this.tasks.get(taskId);
        if (!task) return;
        
        this.currentTask = task;
        this.updateTaskList(Array.from(this.tasks.values()));
        
        // 根据任务状态显示相应界面
        this.updateMainPanel();
    }
    
    // 更新主面板
    updateMainPanel() {
        const ddlSection = document.getElementById('ddl-section');
        const progressSection = document.getElementById('progress-section');
        
        if (!this.currentTask) {
            ddlSection.style.display = 'none';
            progressSection.style.display = 'none';
            return;
        }
        
        const status = this.currentTask.status;
        
        if (status === 'waiting_confirmation') {
            ddlSection.style.display = 'block';
            progressSection.style.display = 'none';
            this.showDDLEditor();
        } else if (['ddl_confirmed', 'importing', 'completed'].includes(status)) {
            ddlSection.style.display = 'none';
            progressSection.style.display = 'block';
            this.showProgressMonitor();
        } else {
            ddlSection.style.display = 'none';
            progressSection.style.display = 'none';
        }
    }
    
    // 显示DDL编辑器
    showDDLEditor() {
        if (!this.currentTask) return;
        
        document.getElementById('table-name').textContent = this.currentTask.table_name || '-';
        document.getElementById('confidence-score').textContent = 
            this.currentTask.confidence_score ? `${(this.currentTask.confidence_score * 100).toFixed(1)}%` : '-';
        
        // 优先从任务中获取estimated_rows，如果没有则从 sample_data 中获取
        const estimatedRows = this.currentTask.estimated_rows || 
                             (this.currentTask.sample_data && this.currentTask.sample_data.estimated_rows);
        document.getElementById('estimated-rows').textContent = 
            estimatedRows ? estimatedRows.toLocaleString() : '-';
        
        const ddlEditor = document.getElementById('ddl-editor');
        ddlEditor.value = this.currentTask.ddl_statement || '';
        
        // 输出调试信息
        console.log('DDL Editor - Current Task:', {
            table_name: this.currentTask.table_name,
            ddl_statement: this.currentTask.ddl_statement,
            confidence_score: this.currentTask.confidence_score,
            estimated_rows: estimatedRows,
            status: this.currentTask.status
        });
    }
    
    // 显示进度监控
    showProgressMonitor() {
        if (!this.currentTask) return;
        
        const status = this.currentTask.status;
        document.getElementById('current-status').textContent = this.getStatusText(status);
        
        const progress = this.currentTask.progress || 0;
        this.updateProgress(progress);
        
        // 显示/隐藏取消按钮
        const cancelBtn = document.getElementById('cancel-import');
        cancelBtn.style.display = status === 'importing' ? 'block' : 'none';
    }
    
    // 更新进度
    updateProgress(percent) {
        const progressFill = document.getElementById('overall-progress');
        const progressText = document.getElementById('overall-progress-text');
        
        progressFill.style.width = `${percent}%`;
        progressText.textContent = `${percent.toFixed(1)}%`;
    }
    
    // 验证DDL
    validateDDL() {
        const ddl = document.getElementById('ddl-editor').value;
        
        if (!ddl.trim()) {
            this.showModal('验证失败', 'DDL语句不能为空', 'warning');
            return;
        }
        
        // 基本语法检查
        if (!ddl.trim().toUpperCase().startsWith('CREATE TABLE')) {
            this.showModal('验证失败', 'DDL语句必须以CREATE TABLE开始', 'warning');
            return;
        }
        
        this.showModal('验证成功', 'DDL语句语法正确', 'success');
        this.log('DDL语句验证通过', 'success');
    }
    
    // 确认DDL
    confirmDDL() {
        const ddl = document.getElementById('ddl-editor').value;
        
        if (!ddl.trim()) {
            this.showModal('确认失败', 'DDL语句不能为空', 'warning');
            return;
        }
        
        if (!this.currentTask) {
            this.showModal('确认失败', '没有选中的任务', 'warning');
            return;
        }
        
        if (this.pollingEnabled) {
            // 轮询模式下使用HTTP请求
            this.confirmDDLViaHTTP(this.currentTask.task_id, ddl);
        } else {
            // WebSocket模式
            this.socket.emit('confirm_ddl', {
                task_id: this.currentTask.task_id,
                ddl_statement: ddl
            });
        }
        
        this.log('DDL语句已确认，开始执行...', 'info');
    }
    
    // 轮询模式下的DDL确认
    async confirmDDLViaHTTP(taskId, ddl) {
        try {
            const response = await fetch('/confirm_ddl', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    task_id: taskId,
                    ddl_statement: ddl
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.log('DDL确认成功', 'success');
            } else {
                this.log(`DDL确认失败: ${result.message}`, 'error');
            }
        } catch (error) {
            this.log(`DDL确认请求失败: ${error.message}`, 'error');
        }
    }
    
    // 修改DDL
    modifyDDL() {
        const ddl = document.getElementById('ddl-editor').value;
        
        if (!this.currentTask) {
            this.showModal('修改失败', '没有选中的任务', 'warning');
            return;
        }
        
        this.socket.emit('modify_ddl', {
            task_id: this.currentTask.task_id,
            ddl_statement: ddl
        });
        
        this.log('DDL语句已修改', 'info');
    }
    
    // 取消导入
    cancelImport() {
        if (!this.currentTask) return;
        
        this.socket.emit('cancel_task', {
            task_id: this.currentTask.task_id
        });
        
        this.log('正在取消导入任务...', 'warning');
    }
    
    // 清空日志
    clearLogs() {
        document.getElementById('log-output').innerHTML = '';
        this.log('日志已清空', 'info');
    }
    
    // 检查待确认的任务（用于重连后恢复状态）
    checkPendingConfirmations() {
        // 查找所有等待确认的任务
        const pendingTasks = Array.from(this.tasks.values()).filter(task => 
            task.status === 'waiting_confirmation' && task.ddl_statement
        );
        
        if (pendingTasks.length > 0) {
            this.log(`发现 ${pendingTasks.length} 个待确认的任务`, 'info');
            
            // 选择最新的任务
            const latestTask = pendingTasks.reduce((latest, current) => 
                (current.created_at || 0) > (latest.created_at || 0) ? current : latest
            );
            
            if (latestTask) {
                this.selectTask(latestTask.task_id);
                this.showDDLEditor();
                this.log(`自动选择最新的待确认任务: ${latestTask.table_name || latestTask.filename}`, 'success');
            }
        }
    }
    
    // SocketIO事件处理器
    handleTaskStarted(data) {
        this.log(`任务开始: ${data.message}`, 'info');
        
        // 加载任务列表，并可能自动选择新任务
        this.loadTasks(() => {
            // 如果当前没有选中任务，尝试选择最新的任务
            if (!this.currentTask && data.task_id) {
                const task = this.tasks.get(data.task_id);
                if (task) {
                    this.selectTask(data.task_id);
                }
            }
        });
    }
    
    handleParsingCompleted(data) {
        this.log(`解析完成: ${data.message}`, 'success');
        this.loadTasks();
    }
    
    handleSchemaInferred(data) {
        this.log(`推断完成: ${data.message}`, 'success');
        
        // 强制重新加载任务并自动选择
        this.loadTasks(() => {
            // 在任务加载完成后，强制选择该任务
            const task = this.tasks.get(data.task_id);
            if (task) {
                // 强制更新任务状态
                task.status = 'waiting_confirmation';
                task.ddl_statement = data.ddl_statement;
                task.confidence_score = data.confidence_score;
                task.table_name = data.table_name;
                
                // 立即选择该任务
                this.selectTask(data.task_id);
                this.log(`自动选择任务: ${task.table_name || task.filename}`, 'info');
                
                // 强制显示DDL编辑器
                this.showDDLEditor();
                
                // 滚动到DDL区域
                document.getElementById('ddl-section').scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'start' 
                });
            } else {
                this.log(`警告：未找到任务 ${data.task_id}`, 'warning');
                // 延迟重试
                setTimeout(() => {
                    this.loadTasks(() => {
                        const retryTask = this.tasks.get(data.task_id);
                        if (retryTask) {
                            this.selectTask(data.task_id);
                            this.showDDLEditor();
                        }
                    });
                }, 1000);
            }
        });
        
        // 如果当前任务是该任务，立即更新
        if (this.currentTask && this.currentTask.task_id === data.task_id) {
            this.currentTask.status = 'waiting_confirmation';
            this.currentTask.ddl_statement = data.ddl_statement;
            this.currentTask.confidence_score = data.confidence_score;
            this.currentTask.table_name = data.table_name;
            this.updateMainPanel();
        }
    }
    
    handleDDLConfirmed(data) {
        this.log(`DDL确认: ${data.message}`, 'success');
        
        if (this.currentTask && this.currentTask.task_id === data.task_id) {
            this.currentTask.status = 'ddl_confirmed';
            this.updateMainPanel();
        }
        
        this.loadTasks();
    }
    
    handleTableCreated(data) {
        this.log(`建表成功: ${data.message}`, 'success');
        
        if (this.currentTask && this.currentTask.task_id === data.task_id) {
            this.currentTask.status = 'importing';
            this.updateMainPanel();
        }
        
        this.loadTasks();
    }
    
    handleImportProgress(data) {
        const progressData = data.progress_data;
        const percent = progressData.progress_percent || 0;
        
        this.updateProgress(percent);
        
        // 更新统计信息
        document.getElementById('completed-tasks').textContent = progressData.completed_tasks || 0;
        document.getElementById('failed-tasks').textContent = progressData.failed_tasks || 0;
        
        this.log(`导入进度: ${percent.toFixed(1)}%`, 'info');
    }
    
    handleImportCompleted(data) {
        this.log(`导入完成: ${data.message}`, data.success ? 'success' : 'error');
        
        // 更新统计信息
        document.getElementById('imported-rows').textContent = data.total_rows?.toLocaleString() || 0;
        document.getElementById('execution-time').textContent = 
            data.execution_time ? `${data.execution_time.toFixed(1)}s` : '0s';
        
        if (this.currentTask && this.currentTask.task_id === data.task_id) {
            this.currentTask.status = data.success ? 'completed' : 'failed';
            this.updateMainPanel();
        }
        
        this.loadTasks();
        
        // 显示完成通知
        this.showModal(
            data.success ? '导入成功' : '导入失败',
            data.message,
            data.success ? 'success' : 'error'
        );
    }
    
    handleTaskFailed(data) {
        this.log(`任务失败: ${data.error_message}`, 'error');
        
        if (this.currentTask && this.currentTask.task_id === data.task_id) {
            this.currentTask.status = 'failed';
            this.updateMainPanel();
        }
        
        this.loadTasks();
        
        this.showModal('任务失败', data.error_message, 'error');
    }
    
    // 工具函数
    getStatusText(status) {
        const statusMap = {
            'parsing': '解析中',
            'inferring': '推断中',
            'waiting_confirmation': '等待确认',
            'ddl_confirmed': '已确认',
            'importing': '导入中',
            'completed': '已完成',
            'failed': '失败',
            'cancelled': '已取消'
        };
        
        return statusMap[status] || status;
    }
    
    // 新增：处理解析进度事件
    handleParsingProgress(data) {
        const stage = data.stage || 'parsing';
        const message = data.message || '正在处理...';
        const progress = data.progress || 0;
        
        // 显示进度信息
        this.log(`[解析进度] ${message} (${progress.toFixed(1)}%)`, 'info');
        
        // 更新进度条（如果有）
        if (stage === 'parsing' && progress > 0) {
            // 可以在这里更新解析进度条
            this.updateProgress(progress / 2); // 解析阶段占总进度的50%
        }
        
        // 如果检测到表名，显示额外信息
        if (data.table_name) {
            this.log(`检测到表名: ${data.table_name}`, 'success');
        }
        
        if (data.estimated_rows) {
            this.log(`估计行数: ${data.estimated_rows.toLocaleString()}`, 'info');
        }
    }
    
    // 新增：处理推断进度事件
    handleInferenceProgress(data) {
        const stage = data.inference_stage || 'inference';
        const message = data.message || '正在推断...';
        const progress = data.progress || 0;
        
        // 显示进度信息
        this.log(`[AI推断] ${message} (${progress.toFixed(1)}%)`, 'info');
        
        // 更新进度条
        if (progress > 0) {
            this.updateProgress(progress);
        }
        
        // 根据推断阶段显示不同信息
        if (stage === 'inference_start') {
            this.log('开始AI表结构推断...', 'info');
        } else if (stage === 'building_prompt') {
            this.log('正在构建推断提示词...', 'info');
        } else if (stage === 'calling_api') {
            this.log('正在调用DeepSeek API...', 'info');
        } else if (stage === 'api_request') {
            this.log('正在发送API请求...', 'info');
        } else if (stage === 'api_response') {
            this.log('正在处理API响应...', 'info');
        } else if (stage === 'parsing_response') {
            this.log('正在解析AI响应...', 'info');
        } else if (stage === 'validating_ddl') {
            this.log('正在验证DDL语句...', 'info');
        } else if (stage === 'inference_completed') {
            this.log('AI推断完成!', 'success');
        } else if (stage === 'api_timeout') {
            this.log('API调用超时', 'warning');
        } else if (stage === 'api_error') {
            this.log('API调用出错', 'error');
        }
        
        // 显示表名信息
        if (data.table_name) {
            this.log(`推断表名: ${data.table_name}`, 'info');
        }
    }
    handleTaskCancelled(data) {
        this.log(`任务已取消: ${data.message}`, 'warning');
        
        if (this.currentTask && this.currentTask.task_id === data.task_id) {
            this.currentTask.status = 'cancelled';
            this.updateMainPanel();
        }
        
        // 隐藏取消按钮
        const cancelBtn = document.getElementById('cancel-import');
        if (cancelBtn) {
            cancelBtn.style.display = 'none';
        }
        
        this.loadTasks();
    }
    
    log(message, type = 'info') {
        const logOutput = document.getElementById('log-output');
        const timestamp = new Date().toLocaleTimeString();
        
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type}`;
        logEntry.innerHTML = `
            <span class="timestamp">[${timestamp}]</span>
            <span class="message">${message}</span>
        `;
        
        logOutput.appendChild(logEntry);
        logOutput.scrollTop = logOutput.scrollHeight;
    }
    
    showModal(title, message, type = 'info') {
        document.getElementById('modal-title').textContent = title;
        document.getElementById('modal-message').textContent = message;
        document.getElementById('status-modal').style.display = 'flex';
    }
    
    // 处理数据库选择
    handleDatabaseSelection(targetDatabase) {
        this.log(`选择目标数据库: ${targetDatabase.toUpperCase()}`, 'info');
        
        // 更新数据库描述信息
        const descriptions = {
            'doris': 'Apache Doris - 高性能分析型数据库，适合OLAP场景',
            'postgresql': 'PostgreSQL - 功能强大的开源关系型数据库'
        };
        
        const descriptionElement = document.getElementById('database-description');
        if (descriptionElement) {
            descriptionElement.textContent = descriptions[targetDatabase] || '选择数据迁移的目标数据库类型';
        }
        
        // 存储当前选择的数据库类型
        this.selectedDatabase = targetDatabase;
        
        // 如果有正在进行的任务，提示用户
        if (this.currentTask && this.currentTask.status !== 'completed' && this.currentTask.status !== 'failed') {
            this.showModal('提示', '更改数据库类型将在下次迁移时生效', 'info');
        }
    }
    
    // 获取当前选择的数据库类型
    getSelectedDatabase() {
        const selectedRadio = document.querySelector('input[name="target-database"]:checked');
        return selectedRadio ? selectedRadio.value : 'doris';
    }
}

// 全局函数
function closeModal() {
    document.getElementById('status-modal').style.display = 'none';
}

// 初始化应用
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new MigrationApp();
});

// 导出给全局使用
window.MigrationApp = MigrationApp;