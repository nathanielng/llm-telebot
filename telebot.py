#!/usr/bin/env python

import boto3
import logging
import requests

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, \
    MessageHandler, filters


# ----- 1. Setup -----
logging.basicConfig(
    filename='llm-telebot.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    level=logging.INFO
)

session = boto3.session.Session()
AWS_REGION = session.region_name
logging.info(f'AWS_REGION = {AWS_REGION}')

requests_client = requests.Session()
secrets_manager = boto3.client('secretsmanager', region_name=AWS_REGION)
ssm = boto3.client('ssm', region_name=AWS_REGION)



# ----- 2. AWS -----
def get_ssm(parameter_name, default_value=None):
    try:
        response = ssm.get_parameter(Name=parameter_name)
        return response['Parameter']['Value']
    except Exception as e:
        print(e)
        return default_value

def get_secret(secret_name):
    try:
        response = secrets_manager.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(e)
        return None

MODEL_ID = get_ssm('/telebot/MODEL_ID')
TELEGRAM_API_KEY = get_secret('/telebot/TELEGRAM_API_KEY')
OPENAI_API_KEY = get_secret('/telebot/OPENAI_API_KEY')
OPENAI_API_BASE = get_ssm('/telebot/OPENAI_API_BASE')
OPENAI_API_URL = f'{OPENAI_API_BASE}/chat/completions'
OPENAI_API_HEADERS = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

logging.info(f'OPENAI_API_BASE = {OPENAI_API_BASE}')



# ----- 3. Large Language Model -----
def invoke_endpoint(prompt):
    body = {
        'model': MODEL_ID,
        'messages': [
            {'role': 'system',
             'content': 'You are a helpful assistant.'},
            {'role': 'user',
             'content': prompt}],
    }
    response = requests_client.post(
        OPENAI_API_URL,
        headers = OPENAI_API_HEADERS,
        json = body
    )
    print(response.json())
    choices = response.json()['choices']

    answer = []
    for choice in choices:
        message = choice['message']
        if message['role'] == 'assistant':
            answer.append(message['content'])
        else:
            answer.append(f"""{message['role']}: {message['content']}""")
    return '\n'.join(answer)



# ----- Telegram -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Bot started. Welcome, {update.effective_user.first_name}!'
        )


async def prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    print(f'Prompt: {prompt}')
    # context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.ChatAction.TYPING)

    try:
        response = invoke_endpoint(prompt)
    except Exception as e:
        response = f'Error: {e}'

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'{response}'
    )


def telegram_bot() -> None:
    application = ApplicationBuilder().token(TELEGRAM_API_KEY).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), prompt_handler))
    application.run_polling()



if __name__ == '__main__':
    telegram_bot()
