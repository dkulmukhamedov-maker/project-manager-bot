#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROJECT MANAGER BOT - Полная интеграция Claude AI + Asana + Telegram
"""

import os
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, Dict, List
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

# ===== КОНФИГУРАЦИЯ =====
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')
ASANA_TOKEN = os.environ.get('ASANA_TOKEN')
TELEGRAM_GROUP_ID = int(os.environ.get('TELEGRAM_GROUP_ID', '-1003922826976'))
YOUR_TELEGRAM_ID = int(os.environ.get('YOUR_TELEGRAM_ID', '123456789'))

# Проекты Asana
PROJECTS = {
    "CTP": "1200054008559908",
    "YPS": "1215529391992046",
    "PRINTER": "1215529256189652",
    "RECRUITING": "1215529255800000"
}

PROJECT_NAMES = {
    "1200054008559908": "CTP - Сдать в аренду офис",
    "1215529391992046": "Закупить ЮПС для Рапида 145",
    "1215529256189652": "Купить принтер для симуляции",
    "1215529255800000": "Рекрутинг Продавцы РНП"
}

PM_MAP = {
    "CTP": "@poytaxtgroup_oz",
    "1200054008559908": "@poytaxtgroup_oz",
    "YPS": "@Joggman",
    "1215529391992046": "@Joggman",
    "PRINTER": "@tedwork",
    "1215529256189652": "@tedwork",
    "RECRUITING": "@poytaxtgroup",
    "1215529255800000": "@poytaxtgroup"
}

# ===== CLAUDE AI =====

class ClaudeAnalyzer:
    """Анализатор задач через Claude AI"""

    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)

    async def analyze_overdue_tasks(self, tasks_data: str) -> str:
        """Анализирует просроченные задачи через Claude"""
        try:
            message = self.client.messages.create(
                model="claude-opus-4",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Вы - помощник по управлению проектами.

Вот данные о просроченных задачах:
{tasks_data}

Проанализируй просроченные задачи для каждого проекта и дай рекомендации."""
                    }
                ]
            )
            return message.content[0].text
        except Exception as e:
            return f"Ошибка Claude: {str(e)}"

    async def analyze_sprint(self, tasks_data: str) -> str:
        """Анализирует задачи для спринт-планирования через Claude"""
        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Вы - эксперт по управлению проектами.

Вот данные о текущих задачах:
{tasks_data}

Определи задачи для каждого проекта на следующую неделю и дай рекомендации."""
                    }
                ]
            )
            return message.content[0].text
        except Exception as e:
            return f"Ошибка Claude: {str(e)}"

# ===== ASANA API =====

async def get_asana_tasks(project_id: str) -> List[Dict]:
    """Получить все задачи из проекта Asana"""
    try:
        headers = {
            "Authorization": f"Bearer {ASANA_TOKEN}",
            "Accept": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            url = f"https://app.asana.com/api/1.0/projects/{project_id}/tasks?opt_fields=name,due_on,completed,assignee,custom_fields"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [])
                else:
                    print(f"Asana API error: {response.status}")
                    return []
    except Exception as e:
        print(f"Ошибка Asana: {str(e)}")
        return []

async def get_all_projects_tasks() -> Dict:
    """Получить задачи всех проектов"""
    all_tasks = {}

    for project_name, project_id in PROJECTS.items():
        tasks = await get_asana_tasks(project_id)
        all_tasks[project_name] = {
            "id": project_id,
            "name": PROJECT_NAMES.get(project_id, project_name),
            "pm": PM_MAP.get(project_id, "Unknown"),
            "tasks": tasks
        }

    return all_tasks

# ===== TELEGRAM БОТ =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "БОТ УПРАВЛЕНИЯ ПРОЕКТАМИ (Claude AI)\n\n"
        "Доступные команды:\n"
        "/report - Анализ просроченных задач\n"
        "/sprint - Планирование спринта\n"
        "/status - Статус проектов\n"
        "/help - Справка"
    )

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /report"""
    user_id = update.effective_user.id

    if user_id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Только администратор может использовать эту команду")
        return

    await update.message.reply_text("Анализ просроченных задач запущен...")

    try:
        all_tasks = await get_all_projects_tasks()
        tasks_summary = "СТАТУС ПРОЕКТОВ:\n\n"

        for project_name, project_data in all_tasks.items():
            tasks_summary += f"Проект: {project_data['name']}\n"
            tasks_summary += f"Всего задач: {len(project_data['tasks'])}\n\n"

        claude = ClaudeAnalyzer(CLAUDE_API_KEY)
        analysis = await claude.analyze_overdue_tasks(tasks_summary)

        full_report = f"АНАЛИЗ ПРОСРОЧЕННЫХ ЗАДАЧ\n\n{analysis}\n\nОжидаем ответы от ПМ"

        await context.bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=full_report
        )

        print("Отчет отправлен в группу")

    except Exception as e:
        error_msg = f"Ошибка: {str(e)}"
        await context.bot.send_message(chat_id=TELEGRAM_GROUP_ID, text=error_msg)
        print(f"Ошибка: {error_msg}")

async def handle_sprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /sprint"""
    user_id = update.effective_user.id

    if user_id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Только администратор может использовать эту команду")
        return

    await update.message.reply_text("Спринт-планирование запущено...")

    try:
        all_tasks = await get_all_projects_tasks()
        tasks_summary = "ДАННЫЕ ДЛЯ ПЛАНИРОВАНИЯ:\n\n"

        for project_name, project_data in all_tasks.items():
            tasks_summary += f"{project_data['name']}\n"
            tasks_summary += f"Задач: {len(project_data['tasks'])}\n\n"

        claude = ClaudeAnalyzer(CLAUDE_API_KEY)
        plan = await claude.analyze_sprint(tasks_summary)

        full_plan = f"СПРИНТ-ПЛАН\n\n{plan}"

        await context.bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=full_plan
        )

        print("План спринта отправлен")

    except Exception as e:
        error_msg = f"Ошибка: {str(e)}"
        await context.bot.send_message(chat_id=TELEGRAM_GROUP_ID, text=error_msg)
        print(f"Ошибка: {error_msg}")

async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    user_id = update.effective_user.id

    if user_id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Только администратор может использовать эту команду")
        return

    try:
        all_tasks = await get_all_projects_tasks()
        status_text = "СТАТУС ПРОЕКТОВ:\n\n"

        for project_name, project_data in all_tasks.items():
            total = len(project_data['tasks'])
            completed = sum(1 for t in project_data['tasks'] if t.get('completed'))
            percent = int((completed / total * 100) if total > 0 else 0)

            status_text += f"{project_data['name']}: {percent}%\n"

        await update.message.reply_text(status_text)

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_text(
        "/report - Анализ просроченных задач\n"
        "/sprint - Планирование спринта\n"
        "/status - Статус проектов\n"
        "/help - Справка"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех сообщений"""
    if update.message.text and update.message.text.startswith('/'):
        command = update.message.text[1:].split()[0]

        if command == 'report':
            await handle_report(update, context)
        elif command == 'sprint':
            await handle_sprint(update, context)
        elif command == 'status':
            await handle_status(update, context)
        elif command == 'help':
            await handle_help(update, context)
        elif command == 'start':
            await start(update, context)

# ===== ГЛАВНАЯ ФУНКЦИЯ =====

def main():
    """Запустить бота"""
    print("=" * 60)
    print("БОТ УПРАВЛЕНИЯ ПРОЕКТАМИ (Claude AI)")
    print("=" * 60)

    if not TELEGRAM_TOKEN:
        print("Ошибка: TELEGRAM_TOKEN не установлен!")
        exit(1)

    if not CLAUDE_API_KEY:
        print("Ошибка: CLAUDE_API_KEY не установлен!")
        exit(1)

    print("\nКонфигурация: OK")
    print(f"Telegram Group: {TELEGRAM_GROUP_ID}")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", handle_report))
    application.add_handler(CommandHandler("sprint", handle_sprint))
    application.add_handler(CommandHandler("status", handle_status))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("\nБот запущен!")
    print("=" * 60)

    application.run_polling()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nБот остановлен")
    except Exception as e:
        print(f"\nОшибка: {str(e)}")
