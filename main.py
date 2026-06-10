#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROJECT MANAGER BOT - Полная интеграция Claude AI + Asana + Telegram
Выполняет реальные задачи управления проектами через Claude AI
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
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Вы - помощник по управлению проектами.

Вот данные о просроченных задачах:
{tasks_data}

ЗАДАЧА:
1. Проанализируй просроченные задачи для каждого проекта
2. Определи критичность (КРИТИЧНО/ВЫСОКАЯ/СРЕДНЯЯ)
3. Предложи вопросы для ПМ
4. Определи рекомендуемые действия

ОТВЕТ в формате:
🔴 [ПРОЕКТ]
   ⚠️ КРИТИЧНОСТЬ: [УРОВЕНЬ]
   📌 Просроченные: [СПИСОК]

❓ ВОПРОСЫ для ПМ:
   1. [ВОПРОС 1]
   2. [ВОПРОС 2]
   3. [ВОПРОС 3]

💡 РЕКОМЕНДАЦИИ:
   - [ДЕЙСТВИЕ 1]
   - [ДЕЙСТВИЕ 2]

Анализируй внимательно и дай полезные рекомендации."""
                    }
                ]
            )
            return message.content[0].text
        except Exception as e:
            return f"❌ Ошибка Claude: {str(e)}"

    async def analyze_sprint(self, tasks_data: str) -> str:
        """Анализирует задачи для спринт-планирования через Claude"""
        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Вы - эксперт по управлению проектами и спринтам.

Вот данные о текущих задачах и статусе проектов:
{tasks_data}

ЗАДАЧА СПРИНТ-ПЛАНИРОВАНИЯ:
1. Определи задачи для каждого проекта на следующую неделю
2. Рекомендуй приоритеты
3. Предложи критерии успеха для каждой задачи
4. Определи потенциальные риски

ОТВЕТ в формате:

📋 СПРИНТ-ПЛАН НА НЕДЕЛЮ

🎯 [ПРОЕКТ 1]
   ПМ: [PM]

   Задача 1: [НАЗВАНИЕ]
   ⏰ Рекомендуемый срок: [ДАТА]
   ✅ Критерий успеха: [КРИТЕРИЙ]
   ⚠️ Риск: [РИСК или "Нет"]

   Задача 2: [НАЗВАНИЕ]
   ...

⚡ ОБЩИЕ РЕКОМЕНДАЦИИ:
   - [РЕКОМЕНДАЦИЯ 1]
   - [РЕКОМЕНДАЦИЯ 2]

Дай полезные и практичные рекомендации."""
                    }
                ]
            )
            return message.content[0].text
        except Exception as e:
            return f"❌ Ошибка Claude: {str(e)}"

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
                    print(f"❌ Asana API error: {response.status}")
                    return []
    except Exception as e:
        print(f"❌ Ошибка Asana: {str(e)}")
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
        "🤖 **БОТ УПРАВЛЕНИЯ ПРОЕКТАМИ (Claude AI)**\n\n"
        "✅ Интегрирован с Claude AI для анализа задач\n\n"
        "📖 Доступные команды:\n"
        "/report - Анализ просроченных задач (Claude AI)\n"
        "/sprint - Планирование спринта (Claude AI)\n"
        "/status - Статус всех проектов\n"
        "/help - Справка",
        parse_mode="Markdown"
    )

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /report - анализ просроченных задач через Claude"""
    user_id = update.effective_user.id

    if user_id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("❌ Только администратор может использовать эту команду")
        return

    await update.message.reply_text(
        "✅ /report запущена!\n\n"
        "🔄 Статус:\n"
        "1️⃣ Загрузка данных из Asana...\n"
        "2️⃣ Анализ Claude AI...\n"
        "3️⃣ Отправка в группу...\n\n"
        "⏳ Результаты будут через 30-60 секунд"
    )

    await context.bot.send_message(
        chat_id=TELEGRAM_GROUP_ID,
        text=f"""
🔍 **ЕЖЕДНЕВНАЯ ПРОВЕРКА ПРОСРОЧЕННЫХ ЗАДАЧ**
📅 {datetime.now().strftime("%d
