@echo off
:: Oracle到Doris数据迁移工具 - Windows后台启动脚本

title Oracle到Doris数据迁移工具 - 后台启动

echo Oracle到Doris数据迁移工具 - 后台启动
echo ==================================
echo.

:: 检查虚拟环境
if not exist "venv\Scripts\activate.bat" (
    echo 错误：虚拟环境不存在，请先运行 start.bat 初始化环境
    pause
    exit /b 1
)

:: 检查配置文件
if not exist "config.yaml" (
    echo 错误：config.yaml配置文件不存在
    pause
    exit /b 1
)

:: 显示启动选项
:menu
echo 请选择后台启动方式:
echo 1. 后台启动服务
echo 2. 安装Windows服务 (需要管理员权限)
echo 3. 查看运行状态
echo 4. 停止后台服务
echo 5. 查看日志
echo 6. 退出
echo.
set /p choice="请输入选择 (1-6): "

if "%choice%"=="1" goto start_background
if "%choice%"=="2" goto install_service
if "%choice%"=="3" goto check_status
if "%choice%"=="4" goto stop_service
if "%choice%"=="5" goto view_logs
if "%choice%"=="6" goto exit
echo 无效选择，请重新输入
goto menu

:start_background
echo.
echo 启动后台服务...

:: 检查是否已经在运行
tasklist | findstr /i "python.exe" | findstr /i "app.py" >nul 2>&1
if not errorlevel 1 (
    echo 警告：服务似乎已在运行
    echo 请先选择选项4停止现有服务
    pause
    goto menu
)

:: 激活虚拟环境并后台启动
call venv\Scripts\activate.bat
start /B python app.py --mode web > migration.log 2>&1

echo ✅ 服务已后台启动
echo 日志文件: %CD%\migration.log
echo 访问地址: http://localhost:5000
echo.
echo 管理命令：
echo   查看进程: tasklist ^| findstr python
echo   查看日志: type migration.log
echo   停止服务: 选择菜单选项4
echo.

:: 等待服务启动
timeout /t 3 >nul

:: 检查服务是否启动成功
tasklist | findstr /i "python.exe" | findstr /i "app.py" >nul 2>&1
if not errorlevel 1 (
    echo ✅ 服务启动成功
) else (
    echo ❌ 服务启动失败，请查看日志
    if exist migration.log (
        echo.
        echo 最近的日志内容：
        powershell -Command "Get-Content migration.log -Tail 10"
    )
)

pause
goto menu

:install_service
echo.
echo 安装Windows服务...
echo.
echo 此功能需要：
echo 1. 管理员权限
echo 2. 安装NSSM工具
echo.
echo NSSM下载地址: https://nssm.cc/download
echo.
echo 手动安装步骤：
echo 1. 下载并解压NSSM
echo 2. 以管理员身份运行命令提示符
echo 3. 进入项目目录
echo 4. 执行以下命令：
echo.
echo    nssm install SQLMigrationTool
echo    Application: %CD%\venv\Scripts\python.exe
echo    Arguments: app.py --mode web
echo    Startup directory: %CD%
echo.
echo    net start SQLMigrationTool
echo.
echo 或者使用PowerShell脚本（以管理员身份运行）：
echo.
echo $serviceName = "SQLMigrationTool"
echo $pythonPath = "%CD%\venv\Scripts\python.exe"
echo $scriptPath = "%CD%\app.py"
echo $workingDir = "%CD%"
echo.
echo if (Get-Service $serviceName -ErrorAction SilentlyContinue) {
echo     Stop-Service $serviceName -Force
echo     sc.exe delete $serviceName
echo }
echo.
echo sc.exe create $serviceName binPath= "$pythonPath $scriptPath --mode web" start= auto
echo sc.exe config $serviceName obj= "LocalSystem"
echo New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\$serviceName" -Name "AppDirectory" -Value $workingDir -PropertyType String -Force
echo Start-Service $serviceName
echo.

pause
goto menu

:check_status
echo.
echo 检查服务运行状态...
echo.

echo 📋 Python进程：
tasklist | findstr /i "python.exe" | findstr /i "app.py"
if errorlevel 1 (
    echo ❌ 未发现Python进程
) else (
    echo ✅ 发现Python进程
)
echo.

echo 🌐 端口状态：
netstat -an | findstr ":5000"
if errorlevel 1 (
    echo ❌ 端口5000未被占用
) else (
    echo ✅ 端口5000已被占用
)
echo.

echo 🔧 Windows服务：
sc query SQLMigrationTool >nul 2>&1
if errorlevel 1 (
    echo ❌ SQLMigrationTool服务未安装
) else (
    sc query SQLMigrationTool
)
echo.

pause
goto menu

:stop_service
echo.
echo 停止后台服务...

set STOPPED=false

:: 停止Python进程
echo 查找并停止Python进程...
for /f "tokens=2" %%i in ('tasklist ^| findstr /i "python.exe" ^| findstr /i "app.py"') do (
    echo 停止进程 %%i
    taskkill /PID %%i /F >nul 2>&1
    set STOPPED=true
)

:: 停止Windows服务
sc query SQLMigrationTool >nul 2>&1
if not errorlevel 1 (
    echo 停止Windows服务...
    net stop SQLMigrationTool >nul 2>&1
    if not errorlevel 1 (
        echo ✅ Windows服务已停止
        set STOPPED=true
    )
)

if "%STOPPED%"=="false" (
    echo ⚠️ 未发现运行中的服务
) else (
    echo ✅ 服务已停止
)

pause
goto menu

:view_logs
echo.
echo 查看日志...
echo.

if exist migration.log (
    echo 📋 显示日志文件最后50行：
    echo =====================================
    powershell -Command "Get-Content migration.log -Tail 50"
    echo =====================================
    echo.
    echo 完整日志文件位置: %CD%\migration.log
    echo 实时查看日志: powershell -Command "Get-Content migration.log -Wait"
) else (
    echo ❌ migration.log文件不存在
)

echo.
pause
goto menu

:exit
echo.
echo 感谢使用！
exit /b 0