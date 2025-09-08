#!/bin/sh

echo "==================================="
echo "Oracle到多数据库迁移工具"
echo "==================================="
echo

# 颜色定义（POSIX兼容）
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查是否在虚拟环境中（POSIX兼容）
if [ "$VIRTUAL_ENV" = "" ]; then
    printf "${RED}错误：请先激活虚拟环境${NC}\n"
    echo "运行以下命令激活虚拟环境："
    echo "source venv/bin/activate"
    echo "然后重新运行此脚本"
    exit 1
fi

printf "${GREEN}检测到虚拟环境: $VIRTUAL_ENV${NC}\n"
printf "${BLUE}Python版本：${NC}"
python --version

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    printf "${YELLOW}警告：config.yaml配置文件不存在${NC}\n"
    if [ -f "config.yaml.example" ]; then
        echo "正在复制示例配置文件..."
        cp config.yaml.example config.yaml
        echo
        printf "${YELLOW}请编辑 config.yaml 文件，配置数据库连接和API密钥${NC}\n"
        echo "然后重新运行此脚本"
        exit 1
    else
        printf "${RED}错误：配置文件和示例文件都不存在${NC}\n"
        exit 1
    fi
fi

# 安装依赖
printf "${BLUE}检查和安装依赖库...${NC}\n"
pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    printf "${RED}错误：安装依赖失败${NC}\n"
    exit 1
fi

# 运行环境检查
printf "${BLUE}运行环境检查...${NC}\n"
python app.py --mode check
if [ $? -ne 0 ]; then
    printf "${YELLOW}环境检查发现问题，请根据提示修复${NC}\n"
    exit 1
fi

echo
printf "${GREEN}环境检查通过！${NC}\n"
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
    printf "请输入选择 (1-6): "
    read choice

    case $choice in
        1)
            echo
            printf "${BLUE}启动Web界面...${NC}\n"
            printf "${GREEN}请在浏览器中访问: http://localhost:5000${NC}\n"
            echo "按 Ctrl+C 停止服务"
            python app.py --mode web
            break
            ;;
        2)
            echo
            printf "${BLUE}启动命令行模式...${NC}\n"
            python app.py --mode cli
            break
            ;;
        3)
            echo
            printf "${BLUE}运行快速测试...${NC}\n"
            python app.py --mode test
            printf "按回车键继续..."
            read dummy
            continue
            ;;
        4)
            echo
            printf "${BLUE}运行系统功能测试...${NC}\n"
            python test_system.py
            printf "按回车键继续..."
            read dummy
            continue
            ;;
        5)
            echo
            printf "${BLUE}运行数据库选择测试...${NC}\n"
            python test_database_selection.py
            printf "按回车键继续..."
            read dummy
            continue
            ;;
        6)
            echo
            printf "${GREEN}感谢使用！${NC}\n"
            exit 0
            ;;
        *)
            printf "${RED}无效选择，请重新输入${NC}\n"
            continue
            ;;
    esac
done