@echo off
chcp 65001 >nul
echo ========================================
echo   EYES-T AI Assistant 启动脚本
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 激活 conda 环境
echo [1/4] 激活 eyes_t 环境...
call conda activate eyes_t
if errorlevel 1 (
    echo [警告] 无法激活 eyes_t 环境，使用当前环境
)

REM 检查依赖
echo [2/4] 检查依赖包...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装依赖包...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

REM 检查 Ollama
echo [3/4] 检查 Ollama 服务...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [警告] Ollama 服务未运行
    echo [提示] 请确保已启动 Ollama: ollama serve
    echo.
    choice /C YN /M "是否继续启动（没有 Ollama 部分功能将不可用）"
    if errorlevel 2 exit /b 0
)

REM 启动应用
echo [4/4] 启动 AI Assistant...
echo.
echo ========================================
echo   系统即将启动...
echo   Web 界面: http://127.0.0.1:5000
echo ========================================
echo.
python app.py

pause

