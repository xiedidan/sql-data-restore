#!/bin/bash

# Oracle到Doris数据迁移工具 - 后台启动脚本
# 支持多种后台启动方式

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${BLUE}Oracle到Doris数据迁移工具 - 后台启动${NC}"
echo "=================================="
echo

# 检查Python和虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${RED}错误：虚拟环境不存在，请先运行 ./start.sh 初始化环境${NC}"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo -e "${RED}错误：config.yaml配置文件不存在${NC}"
    exit 1
fi

# 显示启动选项
echo "请选择后台启动方式:"
echo "1. nohup 后台启动（推荐）"
echo "2. screen 会话启动"
echo "3. systemd 服务启动"
echo "4. 查看运行状态"
echo "5. 停止后台服务"
echo "6. 查看日志"
echo "7. 退出"
echo

while true; do
    read -p "请输入选择 (1-7): " choice
    
    case $choice in
        1)
            echo
            echo -e "${BLUE}使用nohup后台启动...${NC}"
            
            # 检查是否已经在运行
            if pgrep -f "app.py --mode web" > /dev/null; then
                echo -e "${YELLOW}警告：服务似乎已在运行${NC}"
                echo "请先选择选项5停止现有服务"
                continue
            fi
            
            # 后台启动
            nohup python app.py --mode web > migration.log 2>&1 &
            PID=$!
            
            echo -e "${GREEN}✅ 服务已后台启动${NC}"
            echo "进程ID: $PID"
            echo "日志文件: $PROJECT_DIR/migration.log"
            echo "访问地址: http://localhost:5000"
            echo
            echo "管理命令："
            echo "  查看进程: ps aux | grep 'app.py'"
            echo "  查看日志: tail -f migration.log"
            echo "  停止服务: pkill -f 'app.py --mode web'"
            
            # 等待服务启动
            sleep 3
            if pgrep -f "app.py --mode web" > /dev/null; then
                echo -e "${GREEN}✅ 服务启动成功${NC}"
            else
                echo -e "${RED}❌ 服务启动失败，请查看日志${NC}"
                tail -20 migration.log
            fi
            break
            ;;
            
        2)
            echo
            echo -e "${BLUE}使用screen会话启动...${NC}"
            
            # 检查screen是否安装
            if ! command -v screen &> /dev/null; then
                echo -e "${RED}错误：screen未安装${NC}"
                echo "请安装: sudo apt-get install screen  # Ubuntu/Debian"
                echo "       sudo yum install screen     # CentOS/RHEL"
                continue
            fi
            
            # 检查是否已有会话
            if screen -list | grep -q "migration-tool"; then
                echo -e "${YELLOW}警告：migration-tool会话已存在${NC}"
                echo "管理命令："
                echo "  重新连接: screen -r migration-tool"
                echo "  终止会话: screen -S migration-tool -X quit"
                continue
            fi
            
            # 创建screen会话
            screen -dmS migration-tool bash -c "cd '$PROJECT_DIR' && source venv/bin/activate && python app.py --mode web"
            
            echo -e "${GREEN}✅ Screen会话已创建${NC}"
            echo "会话名称: migration-tool"
            echo "访问地址: http://localhost:5000"
            echo
            echo "管理命令："
            echo "  查看会话: screen -list"
            echo "  连接会话: screen -r migration-tool"
            echo "  分离会话: Ctrl+A, D"
            echo "  终止会话: screen -S migration-tool -X quit"
            break
            ;;
            
        3)
            echo
            echo -e "${BLUE}创建systemd服务...${NC}"
            
            # 检查是否有sudo权限
            if ! sudo -n true 2>/dev/null; then
                echo -e "${RED}错误：需要sudo权限创建systemd服务${NC}"
                continue
            fi
            
            # 获取当前用户和组
            USER_NAME=$(whoami)
            GROUP_NAME=$(id -gn)
            PYTHON_PATH="$PROJECT_DIR/venv/bin/python"
            
            # 创建服务文件
            cat << EOF | sudo tee /etc/systemd/system/sql-migration.service > /dev/null
[Unit]
Description=Oracle to Doris Migration Tool
After=network.target

[Service]
Type=simple
User=$USER_NAME
Group=$GROUP_NAME
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PYTHON_PATH app.py --mode web
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
            
            # 重新加载systemd
            sudo systemctl daemon-reload
            sudo systemctl enable sql-migration
            sudo systemctl start sql-migration
            
            echo -e "${GREEN}✅ Systemd服务已创建并启动${NC}"
            echo "服务名称: sql-migration"
            echo "访问地址: http://localhost:5000"
            echo
            echo "管理命令："
            echo "  查看状态: sudo systemctl status sql-migration"
            echo "  查看日志: sudo journalctl -u sql-migration -f"
            echo "  重启服务: sudo systemctl restart sql-migration"
            echo "  停止服务: sudo systemctl stop sql-migration"
            echo "  禁用服务: sudo systemctl disable sql-migration"
            
            # 检查服务状态
            sleep 2
            if sudo systemctl is-active sql-migration >/dev/null; then
                echo -e "${GREEN}✅ 服务运行正常${NC}"
            else
                echo -e "${RED}❌ 服务启动失败${NC}"
                sudo systemctl status sql-migration
            fi
            break
            ;;
            
        4)
            echo
            echo -e "${BLUE}检查服务运行状态...${NC}"
            echo
            
            # 检查nohup进程
            echo "📋 Nohup进程："
            if pgrep -f "app.py --mode web" > /dev/null; then
                ps aux | grep "app.py --mode web" | grep -v grep
                echo -e "${GREEN}✅ 发现nohup进程${NC}"
            else
                echo -e "${YELLOW}❌ 未发现nohup进程${NC}"
            fi
            echo
            
            # 检查screen会话
            echo "📱 Screen会话："
            if command -v screen &> /dev/null; then
                if screen -list | grep -q "migration-tool"; then
                    screen -list | grep "migration-tool"
                    echo -e "${GREEN}✅ 发现screen会话${NC}"
                else
                    echo -e "${YELLOW}❌ 未发现screen会话${NC}"
                fi
            else
                echo -e "${YELLOW}⚠️  Screen未安装${NC}"
            fi
            echo
            
            # 检查systemd服务
            echo "🔧 Systemd服务："
            if [ -f "/etc/systemd/system/sql-migration.service" ]; then
                sudo systemctl status sql-migration --no-pager
            else
                echo -e "${YELLOW}❌ Systemd服务未配置${NC}"
            fi
            echo
            
            # 检查端口占用
            echo "🌐 端口状态："
            if command -v netstat &> /dev/null; then
                if netstat -tlnp 2>/dev/null | grep -q ":5000"; then
                    netstat -tlnp 2>/dev/null | grep ":5000"
                    echo -e "${GREEN}✅ 端口5000已被占用${NC}"
                else
                    echo -e "${YELLOW}❌ 端口5000未被占用${NC}"
                fi
            else
                echo -e "${YELLOW}⚠️  netstat命令不可用${NC}"
            fi
            
            continue
            ;;
            
        5)
            echo
            echo -e "${BLUE}停止后台服务...${NC}"
            
            STOPPED=false
            
            # 停止nohup进程
            if pgrep -f "app.py --mode web" > /dev/null; then
                echo "停止nohup进程..."
                pkill -f "app.py --mode web"
                echo -e "${GREEN}✅ nohup进程已停止${NC}"
                STOPPED=true
            fi
            
            # 停止screen会话
            if command -v screen &> /dev/null && screen -list | grep -q "migration-tool"; then
                echo "停止screen会话..."
                screen -S migration-tool -X quit
                echo -e "${GREEN}✅ screen会话已终止${NC}"
                STOPPED=true
            fi
            
            # 停止systemd服务
            if [ -f "/etc/systemd/system/sql-migration.service" ] && sudo systemctl is-active sql-migration >/dev/null 2>&1; then
                echo "停止systemd服务..."
                sudo systemctl stop sql-migration
                echo -e "${GREEN}✅ systemd服务已停止${NC}"
                STOPPED=true
            fi
            
            if [ "$STOPPED" = false ]; then
                echo -e "${YELLOW}⚠️  未发现运行中的服务${NC}"
            else
                echo -e "${GREEN}✅ 所有服务已停止${NC}"
            fi
            
            continue
            ;;
            
        6)
            echo
            echo -e "${BLUE}查看日志...${NC}"
            echo
            echo "请选择日志类型："
            echo "1. nohup日志"
            echo "2. systemd日志"
            echo "3. 返回主菜单"
            echo
            read -p "请输入选择 (1-3): " log_choice
            
            case $log_choice in
                1)
                    if [ -f "migration.log" ]; then
                        echo -e "${BLUE}显示nohup日志（最后50行，按Ctrl+C退出）：${NC}"
                        tail -50 migration.log
                        echo
                        echo "实时查看日志: tail -f migration.log"
                    else
                        echo -e "${YELLOW}❌ migration.log文件不存在${NC}"
                    fi
                    ;;
                2)
                    if [ -f "/etc/systemd/system/sql-migration.service" ]; then
                        echo -e "${BLUE}显示systemd日志（最后50行）：${NC}"
                        sudo journalctl -u sql-migration -n 50 --no-pager
                        echo
                        echo "实时查看日志: sudo journalctl -u sql-migration -f"
                    else
                        echo -e "${YELLOW}❌ systemd服务未配置${NC}"
                    fi
                    ;;
                3)
                    ;;
                *)
                    echo -e "${RED}无效选择${NC}"
                    ;;
            esac
            
            continue
            ;;
            
        7)
            echo
            echo -e "${GREEN}退出后台启动工具${NC}"
            exit 0
            ;;
            
        *)
            echo -e "${RED}无效选择，请重新输入${NC}"
            continue
            ;;
    esac
done