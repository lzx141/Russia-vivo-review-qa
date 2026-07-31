@echo off
chcp 65001 >nul
echo ========================================
echo 月度数据爬取 - %date% %time%
echo ========================================
cd /d C:\Users\lenovo\Desktop\益普索\Russiadata
python scripts\run_crawler_monthly.py > logs\monthly_crawler_%date:~0,4%%date:~5,2%_%date:~8,2%.log 2>&1
echo 完成: %date% %time%
