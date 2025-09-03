"""
AI推断模块

使用DeepSeek R1 API根据样本数据推断Doris建表语句
"""

import json
import logging
import re
import requests
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from .sql_parser import TableSchema

@dataclass
class InferenceResult:
    """推断结果数据类"""
    success: bool
    ddl_statement: str
    table_name: str
    error_message: str = ""
    confidence_score: float = 0.0
    inference_time: float = 0.0

class SchemaInferenceEngine:
    """表结构推断引擎"""
    
    def __init__(self, config: Dict):
        """
        初始化推断引擎
        
        Args:
            config: 配置字典，包含DeepSeek API配置
        """
        self.config = config
        self.api_config = config.get('deepseek', {})
        self.api_key = self.api_config.get('api_key')
        self.base_url = self.api_config.get('base_url', 'https://api.deepseek.com')
        self.model = self.api_config.get('model', 'deepseek-reasoner')
        self.max_tokens = self.api_config.get('max_tokens', 4000)
        self.temperature = self.api_config.get('temperature', 0.1)
        self.timeout = self.api_config.get('timeout', 30)
        
        self.logger = logging.getLogger(__name__)
        
        if not self.api_key or self.api_key == "your_deepseek_api_key_here":
            self.logger.warning("DeepSeek API密钥未配置，推断功能将不可用")
    
    def infer_table_schema(self, sample_data: Dict, progress_callback: Optional[callable] = None) -> InferenceResult:
        """
        推断表结构
        
        Args:
            sample_data: 从SQLFileParser提取的样本数据
            progress_callback: 进度回调函数
            
        Returns:
            推断结果
        """
        start_time = time.time()
        
        if progress_callback:
            progress_callback({
                'stage': 'inference_start',
                'message': '开始 AI 表结构推断...',
                'progress': 0
            })
        
        try:
            # 构建提示词
            if progress_callback:
                progress_callback({
                    'stage': 'building_prompt',
                    'message': '正在构建 AI 推断提示词...',
                    'progress': 10
                })
            
            prompt = self._build_inference_prompt(sample_data)
            
            # 调用API
            if progress_callback:
                progress_callback({
                    'stage': 'calling_api',
                    'message': '正在调用 DeepSeek API 进行推断...',
                    'progress': 30
                })
            
            api_response = self.call_deepseek_api(prompt, progress_callback)
            
            if not api_response:
                if progress_callback:
                    progress_callback({
                        'stage': 'inference_failed',
                        'message': 'API 调用失败',
                        'progress': 0
                    })
                return InferenceResult(
                    success=False,
                    ddl_statement="",
                    table_name=sample_data.get('table_name', ''),
                    error_message="API调用失败"
                )
            
            # 解析响应
            if progress_callback:
                progress_callback({
                    'stage': 'parsing_response',
                    'message': '正在解析 AI 响应...',
                    'progress': 80
                })
            
            ddl_statement = self.parse_ddl_response(api_response)
            
            # 清理和替换数据库名称
            ddl_statement = self._clean_database_references(ddl_statement)
            
            # 验证DDL语句
            if progress_callback:
                progress_callback({
                    'stage': 'validating_ddl',
                    'message': '正在验证 DDL 语句...',
                    'progress': 90
                })
            
            is_valid = self.validate_doris_ddl(ddl_statement)
            
            inference_time = time.time() - start_time
            
            if progress_callback:
                progress_callback({
                    'stage': 'inference_completed',
                    'message': f'推断完成，耗时 {inference_time:.2f}秒',
                    'progress': 100
                })
            
            return InferenceResult(
                success=is_valid,
                ddl_statement=ddl_statement,
                table_name=sample_data.get('table_name', ''),
                confidence_score=0.9 if is_valid else 0.3,
                inference_time=inference_time
            )
            
        except Exception as e:
            self.logger.error(f"推断表结构失败: {str(e)}")
            if progress_callback:
                progress_callback({
                    'stage': 'inference_error',
                    'message': f'推断出错: {str(e)}',
                    'progress': 0
                })
            return InferenceResult(
                success=False,
                ddl_statement="",
                table_name=sample_data.get('table_name', ''),
                error_message=str(e),
                inference_time=time.time() - start_time
            )
    
    def call_deepseek_api(self, prompt: str, progress_callback: Optional[callable] = None) -> Optional[str]:
        """
        调用DeepSeek API
        
        Args:
            prompt: 提示词
            progress_callback: 进度回调函数
            
        Returns:
            API响应内容
        """
        if not self.api_key or self.api_key == "your_deepseek_api_key_here":
            self.logger.error("DeepSeek API密钥未配置")
            return None
            
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'stream': False
        }
        
        try:
            self.logger.info("调用DeepSeek API进行表结构推断...")
            
            if progress_callback:
                progress_callback({
                    'stage': 'api_request',
                    'message': '正在发送 API 请求...',
                    'progress': 35
                })
            
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            
            if progress_callback:
                progress_callback({
                    'stage': 'api_response',
                    'message': '正在处理 API 响应...',
                    'progress': 65
                })
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                self.logger.info("DeepSeek API调用成功")
                
                if progress_callback:
                    progress_callback({
                        'stage': 'api_success',
                        'message': 'API 调用成功，正在处理响应...',
                        'progress': 75
                    })
                
                return content
            else:
                self.logger.error(f"DeepSeek API调用失败: {response.status_code}, {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            self.logger.error("DeepSeek API调用超时")
            if progress_callback:
                progress_callback({
                    'stage': 'api_timeout',
                    'message': 'API 调用超时',
                    'progress': 0
                })
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"DeepSeek API网络错误: {str(e)}")
            if progress_callback:
                progress_callback({
                    'stage': 'api_network_error',
                    'message': f'API 网络错误: {str(e)}',
                    'progress': 0
                })
            return None
        except Exception as e:
            self.logger.error(f"DeepSeek API调用异常: {str(e)}")
            if progress_callback:
                progress_callback({
                    'stage': 'api_error',
                    'message': f'API 调用异常: {str(e)}',
                    'progress': 0
                })
            return None
    
    def parse_ddl_response(self, api_response: str) -> str:
        """
        解析API响应中的DDL语句
        
        Args:
            api_response: API响应内容
            
        Returns:
            提取的DDL语句
        """
        if not api_response:
            return ""
            
        # 尝试提取SQL代码块
        # 查找```sql 或 ``` 包围的代码块
        sql_patterns = [
            r'```sql\s*(.*?)\s*```',
            r'```\s*(CREATE TABLE.*?;)\s*```',
            r'(CREATE TABLE[^;]*;)',
        ]
        
        for pattern in sql_patterns:
            match = re.search(pattern, api_response, re.DOTALL | re.IGNORECASE)
            if match:
                ddl = match.group(1).strip()
                if ddl:
                    return ddl
        
        # 如果没有找到代码块，尝试直接提取CREATE TABLE语句
        lines = api_response.split('\n')
        ddl_lines = []
        in_create_table = False
        
        for line in lines:
            line = line.strip()
            if line.upper().startswith('CREATE TABLE'):
                in_create_table = True
                ddl_lines.append(line)
            elif in_create_table:
                ddl_lines.append(line)
                if line.endswith(';'):
                    break
        
        if ddl_lines:
            return '\n'.join(ddl_lines)
        
        # 最后尝试返回整个响应（可能AI直接返回了DDL）
        if 'CREATE TABLE' in api_response.upper():
            return api_response.strip()
            
        return ""
    
    def validate_doris_ddl(self, ddl_statement: str) -> bool:
        """
        验证Doris DDL语句的有效性
        
        Args:
            ddl_statement: DDL语句
            
        Returns:
            是否有效
        """
        if not ddl_statement:
            return False
            
        ddl_upper = ddl_statement.upper()
        
        # 基本结构检查
        if not ddl_upper.startswith('CREATE TABLE'):
            return False
            
        # 检查是否包含表名
        if not re.search(r'CREATE\s+TABLE\s+\w+', ddl_statement, re.IGNORECASE):
            return False
            
        # 检查是否有列定义
        if '(' not in ddl_statement or ')' not in ddl_statement:
            return False
            
        # 检查Doris特定语法（可选）
        # 这里可以添加更多Doris特定的验证规则
        
        return True
    
    def _build_inference_prompt(self, sample_data: Dict) -> str:
        """
        构建推断提示词
        
        Args:
            sample_data: 样本数据
            
        Returns:
            构建的提示词
        """
        table_name = sample_data.get('table_name', 'unknown_table')
        sample_lines = sample_data.get('sample_data', [])
        estimated_rows = sample_data.get('estimated_rows', 0)
        
        # 从样本中提取有效的INSERT语句
        insert_statements = []
        for line in sample_lines:
            if line.strip().upper().startswith('INSERT'):
                insert_statements.append(line.strip())
                if len(insert_statements) >= 5:  # 最多5个样本
                    break
        
        prompt = f"""请基于以下Oracle导出的SQL INSERT语句样本，为Apache Doris数据库生成对应的CREATE TABLE语句。

表名: {table_name}
估计总行数: {estimated_rows}

SQL样本:
"""
        
        for i, stmt in enumerate(insert_statements, 1):
            # 截断过长的语句
            if len(stmt) > 500:
                stmt = stmt[:500] + "..."
            prompt += f"{i}. {stmt}\n"
        
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
        
        return prompt
    
    def get_fallback_ddl(self, table_name: str, sample_data: List[str]) -> str:
        """
        当API调用失败时的备用DDL生成方案
        
        Args:
            table_name: 表名
            sample_data: 样本数据
            
        Returns:
            基础DDL语句
        """
        # 简单的备用方案：生成一个基础的表结构
        ddl = f"""CREATE TABLE {table_name} (
    id BIGINT,
    data TEXT,
    created_time DATETIME
) 
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);"""
        
        self.logger.info(f"使用备用DDL方案为表 {table_name}")
        return ddl
    
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