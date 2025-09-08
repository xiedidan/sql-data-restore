#!/bin/bash

echo "==================================="
echo "Oracle到多数据库迁移工具"
echo "==================================="
echo

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查是否在虚拟环境中
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${RED}错误：请先激活虚拟环境${NC}"
    echo "运行以下命令激活虚拟环境："
    echo "source venv/bin/activate"
    echo "然后重新运行此脚本"
    exit 1
fi

echo -e "${GREEN}检测到虚拟环境: $VIRTUAL_ENV${NC}"
echo -e "${BLUE}Python版本：${NC}$(python --version)"

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo -e "${YELLOW}警告：config.yaml配置文件不存在${NC}"
    if [ -f "config.yaml.example" ]; then
        echo "正在复制示例配置文件..."
        cp config.yaml.example config.yaml
        echo
        echo -e "${YELLOW}请编辑 config.yaml 文件，配置数据库连接和API密钥${NC}"
        echo "然后重新运行此脚本"
        exit 1
    else
        echo -e "${RED}错误：配置文件和示例文件都不存在${NC}"
        exit 1
    fi
fi

# 安装依赖
echo -e "${BLUE}检查和安装依赖库...${NC}"
pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo -e "${RED}错误：安装依赖失败${NC}"
    exit 1
fi

# 运行环境检查
echo -e "${BLUE}运行环境检查...${NC}"
python app.py --mode check
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}环境检查发现问题，请根据提示修复${NC}"
    exit 1
fi

echo
echo -e "${GREEN}环境检查通过！${NC}"
echo

# 显示启动选项
while true; do
    echo "请选择启动模式:"
    echo "1. Web界面模式 (推荐)"
    echo "2. 命令行模式"
    echo "3. 快速测试"
    echo "4. 系统功能测试"
    echo "5. 数据库选择测试"
    echo "6. 退出"
    echo
    read -p "请输入选择 (1-6): " choice

    case $choice in
        1)
            echo
            echo -e "${BLUE}启动Web界面...${NC}"
            echo -e "${GREEN}请在浏览器中访问: http://localhost:5000${NC}"
            echo "按 Ctrl+C 停止服务"
            python app.py --mode web
            break
            ;;
        2)
            echo
            echo -e "${BLUE}启动命令行模式...${NC}"
            python app.py --mode cli
            break
            ;;
        3)
            echo
            echo -e "${BLUE}运行快速测试...${NC}"
            python app.py --mode test
            read -p "按回车键继续..."
            continue
            ;;
        4)
            echo
            echo -e "${BLUE}运行系统功能测试...${NC}"
            python test_system.py
            read -p "按回车键继续..."
            continue
            ;;
        5)
            echo
            echo -e "${BLUE}运行数据库选择测试...${NC}"
            python test_database_selection.py
            read -p "按回车键继续..."
            continue
            ;;
        6)
            echo
            echo -e "${GREEN}感谢使用！${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}无效选择，请重新输入${NC}"
            continue
            ;;
    esac
done