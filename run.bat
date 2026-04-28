@echo off
echo ==============================================
echo   HealthLock Federated Dashboard Startup
echo ==============================================

echo Setting up virtual environment...
python -m venv venv
call venv\Scripts\activate

echo Installing requirements...
pip install -r requirements.txt

echo.
echo Starting Flask server...
python app.py
pause
