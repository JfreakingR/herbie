@echo off
setlocal enabledelayedexpansion

cd /d "C:\Users\Phyllis\Desktop\Herbie"

echo.
echo ========================================
echo Adding files to git repository
echo ========================================
echo.

git add "_qa_enb_manual"
git add "_qa_enb_manual_v2"
git add "_qa_enb_manual_v3"
git add "_qa_enb_manual_v4"
git add "_local_before_github_2026-09-16"
git add ".android"
git add ".build"
git add ".codex"
git add ".codex-remote-attachments"
git add ".serena"
git add ".tools"
git add "androguard.db"
git add "androguard.log"
git add "attachments.zip"
git add "RECOVERED_CODEX_CHAT_2026-09-16.md"
git add "HERBIE_HANDOFF_2026-09-17_REBOOTS_AND_DRIVE_REFUSAL.md"
git add "HERBIE_HANDOFF_2026-09-18_SEQUENCE_AND_IR.md"

echo.
echo ========================================
echo Git Status
echo ========================================
git status

echo.
echo ========================================
echo Committing changes
echo ========================================
git commit -m "Add untracked files: QA manuals, backups, caches, logs, and handoff docs"

echo.
echo ========================================
echo Pushing to GitHub
echo ========================================
git push origin master

echo.
echo ========================================
echo COMPLETE!
echo ========================================
echo All files have been added to GitHub.
echo.
pause
