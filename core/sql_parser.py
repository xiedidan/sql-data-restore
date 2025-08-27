"""
SQL文件解析模块

负责解析Oracle导出的SQL文件，提取样本数据用于AI推断表结构
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class TableSchema:
    """表结构数据类"""
    table_name: str
    ddl_statement: str
    sample_data: List[str]
    column_count: int
    estimated_rows: int

class SQLFileParser:
    """SQL文件解析器"""
    
    def __init__(self, config: Dict):
        """
        初始化SQL文件解析器
        
        Args:
            config: 配置字典，包含sample_lines等参数
        """
        self.config = config
        self.sample_lines = config.get('migration', {}).get('sample_lines', 100)
        self.logger = logging.getLogger(__name__)
        
    def extract_sample_data(self, file_path: str, n_lines: Optional[int] = None) -> Dict:
        """
        提取SQL文件的样本数据
        
        Args:
            file_path: SQL文件路径
            n_lines: 要提取的行数，默认使用配置中的值
            
        Returns:
            包含表名、样本数据等信息的字典
        """
        if n_lines is None:
            n_lines = self.sample_lines
            
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"SQL文件不存在: {file_path}")
            
        try:
            sample_data = []
            table_name = None
            total_lines = 0
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    total_lines += 1
                    
                    # 提取样本行
                    if i < n_lines:
                        sample_data.append(line.strip())
                        
                        # 尝试识别表名
                        if table_name is None:
                            extracted_table = self._extract_table_name_from_line(line)
                            if extracted_table:
                                table_name = extracted_table
                    
                    # 只统计总行数，不全部读取
                    if i >= n_lines and i % 10000 == 0:
                        continue
                        
            # 如果没有从INSERT语句中提取到表名，尝试从文件名推断
            if table_name is None:
                table_name = self._extract_table_name_from_filename(file_path)
                
            # 估算文件大小和行数
            file_size = os.path.getsize(file_path)
            estimated_rows = self._estimate_total_rows(file_path, sample_data)
            
            self.logger.info(f"成功解析SQL文件: {file_path}, 表名: {table_name}, 样本行数: {len(sample_data)}")
            
            return {
                'file_path': file_path,
                'table_name': table_name,
                'sample_data': sample_data,
                'file_size': file_size,
                'estimated_rows': estimated_rows,
                'total_lines': total_lines
            }
            
        except Exception as e:
            self.logger.error(f"解析SQL文件失败: {file_path}, 错误: {str(e)}")
            raise
    
    def identify_table_name(self, sql_content: str) -> str:
        """
        从SQL内容中识别表名
        
        Args:
            sql_content: SQL内容字符串
            
        Returns:
            表名字符串
        """
        # 尝试多种模式匹配INSERT语句中的表名
        patterns = [
            r'INSERT\s+INTO\s+(["`]?)(\w+)\1\s*\(',
            r'INSERT\s+INTO\s+(["`]?)(\w+)\1\s+VALUES',
            r'INSERT\s+INTO\s+(["`]?)(\w+)\1\s+\(',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sql_content, re.IGNORECASE)
            if match:
                return match.group(2)
                
        return None
    
    def extract_insert_statements(self, file_path: str, limit: int = 10) -> List[str]:
        """
        提取INSERT语句样本
        
        Args:
            file_path: SQL文件路径
            limit: 最大提取数量
            
        Returns:
            INSERT语句列表
        """
        insert_statements = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                current_statement = ""
                
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # 检查是否是INSERT语句开始
                    if line.upper().startswith('INSERT'):
                        if current_statement:
                            # 保存之前的语句
                            insert_statements.append(current_statement)
                            if len(insert_statements) >= limit:
                                break
                        current_statement = line
                    else:
                        # 继续拼接当前语句
                        current_statement += " " + line
                        
                    # 检查语句是否结束（以分号结尾）
                    if current_statement.endswith(';'):
                        insert_statements.append(current_statement)
                        if len(insert_statements) >= limit:
                            break
                        current_statement = ""
                        
                # 添加最后一个语句（如果存在）
                if current_statement and len(insert_statements) < limit:
                    insert_statements.append(current_statement)
                    
        except Exception as e:
            self.logger.error(f"提取INSERT语句失败: {file_path}, 错误: {str(e)}")
            
        return insert_statements
    
    def validate_sql_format(self, sql_content: str) -> bool:
        """
        验证SQL格式是否正确
        
        Args:
            sql_content: SQL内容
            
        Returns:
            是否为有效格式
        """
        if not sql_content:
            return False
            
        # 检查是否包含INSERT语句
        if not re.search(r'INSERT\s+INTO', sql_content, re.IGNORECASE):
            return False
            
        # 检查基本语法结构
        if not re.search(r'VALUES\s*\(', sql_content, re.IGNORECASE):
            return False
            
        return True
    
    def get_column_info_from_sample(self, sample_data: List[str]) -> Dict:
        """
        从样本数据中推断列信息
        
        Args:
            sample_data: 样本数据行列表
            
        Returns:
            包含列信息的字典
        """
        column_info = {
            'column_count': 0,
            'sample_values': [],
            'value_patterns': []
        }
        
        # 查找第一个有效的INSERT语句
        for line in sample_data:
            if line.upper().strip().startswith('INSERT'):
                # 提取VALUES部分
                values_match = re.search(r'VALUES\s*\((.*?)\)', line, re.IGNORECASE | re.DOTALL)
                if values_match:
                    values_str = values_match.group(1)
                    # 简单解析值（这里做基础处理，复杂情况由AI处理）
                    values = self._parse_values_string(values_str)
                    column_info['column_count'] = len(values)
                    column_info['sample_values'].append(values)
                    
                    if len(column_info['sample_values']) >= 5:  # 收集足够样本
                        break
                        
        return column_info
    
    def _extract_table_name_from_line(self, line: str) -> Optional[str]:
        """从单行SQL中提取表名"""
        line = line.strip()
        if line.upper().startswith('INSERT'):
            return self.identify_table_name(line)
        return None
    
    def _extract_table_name_from_filename(self, file_path: str) -> str:
        """从文件名推断表名"""
        filename = os.path.basename(file_path)
        # 移除扩展名
        table_name = os.path.splitext(filename)[0]
        # 清理特殊字符
        table_name = re.sub(r'[^\w]', '_', table_name)
        return table_name
    
    def _estimate_total_rows(self, file_path: str, sample_data: List[str]) -> int:
        """估算总行数"""
        try:
            file_size = os.path.getsize(file_path)
            
            # 计算样本数据的平均行长度
            sample_lines = [line for line in sample_data if line.strip()]
            if not sample_lines:
                return 0
                
            avg_line_length = sum(len(line.encode('utf-8')) for line in sample_lines) / len(sample_lines)
            
            # 估算总行数
            estimated_rows = int(file_size / avg_line_length) if avg_line_length > 0 else 0
            
            return estimated_rows
            
        except Exception as e:
            self.logger.warning(f"估算行数失败: {str(e)}")
            return 0
    
    def _parse_values_string(self, values_str: str) -> List[str]:
        """
        解析VALUES字符串中的值
        这是一个简化版本，复杂情况由AI处理
        """
        values = []
        current_value = ""
        in_quotes = False
        quote_char = None
        
        i = 0
        while i < len(values_str):
            char = values_str[i]
            
            if char in ("'", '"') and not in_quotes:
                in_quotes = True
                quote_char = char
                current_value += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current_value += char
            elif char == ',' and not in_quotes:
                values.append(current_value.strip())
                current_value = ""
            else:
                current_value += char
                
            i += 1
            
        # 添加最后一个值
        if current_value.strip():
            values.append(current_value.strip())
            
        return values