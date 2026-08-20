@echo off
cd /d "D:\ic\master project\project_code\KG_construction"
"D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true > streamlit_run.log 2>&1
echo Streamlit exited with code %ERRORLEVEL% >> streamlit_run.log
pause
