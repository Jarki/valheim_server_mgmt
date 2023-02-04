import json
import os
import logging
import time

import requests

import aws_utils
import utils
from botocore.exceptions import ClientError

class Bot:
    def __init__(self, token, api_key) -> None:
        self.token = token
        self.api_key = api_key
        self.prefix = "https://api.telegram.org/bot"
        self.message_handlers = {}
        
    def send_message(self, chat_id, message):
        return requests.get(f"{self.prefix}{token}/sendMessage", params={
            'chat_id': chat_id,
            'text': message,
            'parse_mode':'MarkdownV2'
        })
        
    def add_command_handler(self, callback, command):
        self.message_handlers[command] = callback
        
    def handle_message(self, chat_id, message):
        received_text = message["text"]
        
        if received_text in self.message_handlers:
            self.message_handlers[received_text](chat_id, message)

token = os.environ.get("TELEGRAM_TOKEN")
api_key = os.environ.get("SECRET_API_KEY")
region = os.environ.get("REGION")
instance_id = os.environ.get("INSTANCE_ID")
owner_id = int(os.environ.get("OWNER_ID"))

# TODO:
# 1. Log who uses the command to a DynamoDB table, and send it to owner chat
# 2. Implement allowed users
# 3. Implement admin users
# 4. Figure out names in template (change helloWorld stuff) - DONE
# 5. implement server start-stop, status - DONE

def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """
    
    if event["headers"]["X-Telegram-Bot-Api-Secret-Token"] != api_key:
        return {
            "statusCode": 403,
            "body": "Forbidden"
        }
    
    try:
        update = json.loads(event["body"])
        message = update["message"]
        
        # if message["from"]["id"] != owner_id:
        #     return {
        #         "statusCode": 403,
        #         "body": "Forbidden"
        #     }
        
        bot = Bot(token, api_key)
        
        def start_server(chat_id, message):
            try:
                if aws_utils.get_instance_status(region, instance_id).lower() == 'running':
                    public_ip = aws_utils.get_public_ip(region, instance_id)
                    bot.send_message(owner_id, f"Server is already running\\!\n" + 
                                    f"Use this IP to connect:\n||{utils.escape_string(public_ip)}||")
                    return
                
                bot.send_message(chat_id, f"Starting server")
                
                public_ip = aws_utils.get_public_ip(region, instance_id)
                bot.send_message(chat_id, f"Instance started, starting Valheim dedicated server\nYou will be able to connect shortly\n" +
                                f"Use this IP to connect:\n||{utils.escape_string(public_ip)}||")
                aws_utils.start_valheim_server(region, instance_id)
                
                # Notify the owner
                if chat_id != owner_id:
                    bot.send_message(owner_id, f"Server started by @{utils.escape_string(message['from']['username'])}\n")
            except ClientError as e:
                print(e)
                bot.send_message(chat_id, "An error occured while starting the server")
            except Exception as e:
                print("Unexpected exception:")
                print(e)
            
        def stop_server(chat_id, message):
            try:
                if aws_utils.get_instance_status(region, instance_id).lower() == 'stopped':
                    bot.send_message(owner_id, f"Server is not running\\!\n")
                    return
                
                bot.send_message(chat_id, "Stopping server")
                aws_utils.stop_instance(region, instance_id)
                bot.send_message(chat_id, "Server stopped")
                
                # Notify the owner
                if chat_id != owner_id:
                    bot.send_message(owner_id, f"Server stopped by @{utils.escape_string(message['from']['username'])}\n")
            except ClientError as e:
                print(e)
                bot.send_message(chat_id, "An error occured while stopping the server")
            except Exception as e:
                print("Unexpected exception:")
                print(e)
            
        def get_server_status(chat_id, message):
            try:
                status = aws_utils.get_instance_status(region, instance_id)
                
                message = f"The server is {utils.escape_string(status)}\\.\n"   
                        
                if status == 'running':
                    public_ip = aws_utils.get_public_ip(region, instance_id)
                    message = message + f"Use ||{utils.escape_string(public_ip)}|| to connect\n"
                    
                    usage = aws_utils.get_instance_usage(region, instance_id)
                    # if one is None, the other one is None too
                    if usage['avg'] is not None:
                        message = message + f"CPU usage \\(peak\\): {utils.escape_string(str(round(usage['max'], 3)))}%\n"
                        message = message + f"CPU usage \\(average\\): {utils.escape_string(str(round(usage['avg'], 3)))}%\n"
                
                bot.send_message(chat_id, message)
            except ClientError as e:
                print(e)
                bot.send_message(chat_id, "An error occured while retrieving server status")
            except Exception as e:
                print("Unexpected exception:")
                print(e)
        
        bot.add_command_handler(start_server, "/start_server")
        bot.add_command_handler(stop_server, "/stop_server")
        bot.add_command_handler(get_server_status, "/server_status")
        
        bot.handle_message(message["chat"]["id"], message)
    except Exception as e:
        print(type(e))
        print(str(e))
        return {
            "statusCode": 500,
            "body": "Server failed"
        }
    
    return {
        "statusCode": 200,
        "body": "OK"
    }
