/**
 * Oracle到Doris迁移工具 - 前端JavaScript
 */

class MigrationApp {
    constructor() {
        this.socket = null;
        this.currentTask = null;
        this.tasks = new Map();
        
        this.init();
    }
    
    init() {
        this.initSocketIO();
        this.initEventListeners();
        this.initFileUpload();
        this.loadTasks();
        
        this.log('系统初始化完成', 'info');
    }
    
    // SocketIO初始化
    initSocketIO() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            this.updateConnectionStatus(true);
            this.log('连接到服务器成功', 'success');
        });
        
        this.socket.on('disconnect', () => {
            this.updateConnectionStatus(false);
            this.log('服务器连接断开', 'warning');
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
        
        this.socket.on('error', (data) => {
            this.showModal('错误', data.message, 'error');
            this.log(`错误: ${data.message}`, 'error');
        });
    }
    
    // 事件监听器
    initEventListeners() {
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
    
    // 加载任务列表
    loadTasks() {
        fetch('/tasks')
        .then(response => response.json())
        .then(data => {
            this.updateTaskList(data.tasks);
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
        document.getElementById('estimated-rows').textContent = 
            this.currentTask.estimated_rows?.toLocaleString() || '-';
        
        const ddlEditor = document.getElementById('ddl-editor');
        ddlEditor.value = this.currentTask.ddl_statement || '';
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
        
        this.socket.emit('confirm_ddl', {
            task_id: this.currentTask.task_id,
            ddl_statement: ddl
        });
        
        this.log('DDL语句已确认，开始执行...', 'info');
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
    
    // SocketIO事件处理器
    handleTaskStarted(data) {
        this.log(`任务开始: ${data.message}`, 'info');
        this.loadTasks();
    }
    
    handleParsingCompleted(data) {
        this.log(`解析完成: ${data.message}`, 'success');
        this.loadTasks();
    }
    
    handleSchemaInferred(data) {
        this.log(`推断完成: ${data.message}`, 'success');
        
        // 更新当前任务
        if (this.currentTask && this.currentTask.task_id === data.task_id) {
            this.currentTask.status = 'waiting_confirmation';
            this.currentTask.ddl_statement = data.ddl_statement;
            this.currentTask.confidence_score = data.confidence_score;
            this.updateMainPanel();
        }
        
        this.loadTasks();
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