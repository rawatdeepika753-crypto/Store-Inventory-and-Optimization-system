@echo off
REM Starts the Streamlit web interface of the Store Inventory System.
cd /d "%~dp0"
python -m pip install -r requirements.txt --quiet
python -m streamlit run app.py
pause
