@echo off
chcp 65001 >nul
echo ========================================
echo   BIXOLON 라벨 프린터 빌드
echo ========================================
echo.

echo [1단계] PyInstaller 설치...
C:\Users\kijus\AppData\Local\Programs\Python\Python313\python.exe -m pip install pyinstaller

echo.
echo [2단계] 실행 파일 생성 중...
C:\Users\kijus\AppData\Local\Programs\Python\Python313\python.exe -m PyInstaller --onefile --windowed --name=BixolonLabelPrinter --icon=img/logo.ico  --add-data="img;img" --hidden-import=win32timezone bixolon_label_printer_v2.py
echo.
echo ========================================
echo   완료!
========================================
echo.
echo 실행 파일: dist\BixolonLabelPrinter.exe
echo.
pause