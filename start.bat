@echo off
echo ===================================
echo Oracle到Doris数据迁移工具
echo ===================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：Python未安装或不在PATH中
    echo 请从 https://www.python.org/ 下载并安装Python 3.8+
    pause
    exit /b 1
)

:: 检查配置文件
if not exist "config.yaml" (
    echo 警告：config.yaml配置文件不存在
    if exist "config.yaml.example" (
        echo 正在复制示例配置文件...
        copy "config.yaml.example" "config.yaml"
        echo.
        echo 请编辑 config.yaml 文件，配置数据库连接和API密钥
        echo 然后重新运行此脚本
        pause
        exit /b 1
    ) else (
        echo 错误：配置文件和示例文件都不存在
        pause
        exit /b 1
    )
)

:: 检查虚拟环境
if not exist "venv\Scripts\activate.bat" (
    echo 创建Python虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo 错误：创建虚拟环境失败
        pause
        exit /b 1
    )
)

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 安装依赖
echo 检查和安装依赖库...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo 错误：安装依赖失败
    pause
    exit /b 1
)

:: 运行环境检查
echo 运行环境检查...
python app.py --mode check
if errorlevel 1 (
    echo 环境检查发现问题，请根据提示修复
    pause
    exit /b 1
)

echo.
echo 环境检查通过！
echo.

:: 显示启动选项
:menu
echo 请选择启动模式:
echo 1. Web界面模式 (推荐)
echo 2. 命令行模式
echo 3. 快速测试
echo 4. 退出
echo.
set /p choice="请输入选择 (1-4): "

if "%choice%"=="1" goto web_mode
if "%choice%"=="2" goto cli_mode
if "%choice%"=="3" goto test_mode
if "%choice%"=="4" goto exit
echo 无效选择，请重新输入
goto menu

:web_mode
echo.
echo 启动Web界面...
echo 请在浏览器中访问: http://localhost:5000
echo 按 Ctrl+C 停止服务
python app.py --mode web
goto exit

:cli_mode
echo.
echo 启动命令行模式...
python app.py --mode cli
goto exit

:test_mode
echo.
echo 运行快速测试...
python app.py --mode test
pause
goto menu

:exit
echo.
echo 感谢使用！
pause