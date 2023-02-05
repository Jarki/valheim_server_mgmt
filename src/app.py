import json
import os
import logging

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
        
        self.update_handled = False
        
    def send_message(self, chat_id, message):
        responce = requests.get(f"{self.prefix}{token}/sendMessage", params={
            'chat_id': chat_id,
            'text': message,
            'parse_mode':'MarkdownV2'
        })
         
        logging.info("Sent a message, responce: %s", responce.text)
         
        return responce
        
    def add_command_handler(self, callback, command):
        self.message_handlers[command] = callback
        
    def handle_message(self, chat_id, message):
        logging.info('Handling message from %s (Message: %s)', message["from"]["username"], message["text"])

        if self.update_handled:
            logging.info('Update has already been handled')
            return
            
        received_text = message["text"]
        
        if received_text in self.message_handlers:
            self.message_handlers[received_text](chat_id, message)
            
        self.update_handled = True
        

token = os.environ.get("TELEGRAM_TOKEN")
api_key = str(os.environ.get("SECRET_API_KEY"))
region = os.environ.get("REGION")
instance_id = os.environ.get("INSTANCE_ID")
owner_id = int(os.environ.get("OWNER_ID"))
DEV = int(os.environ.get("DEV"))

# TODO:
# 1. Log who uses the command to a DynamoDB table, and send it to owner chat
# 2. Implement allowed users
# 3. Implement admin users

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    if event["headers"]["X-Telegram-Bot-Api-Secret-Token"] != api_key:
        logging.info("Received an api key that ends with %s", event["headers"]["X-Telegram-Bot-Api-Secret-Token"][-4:])
        logging.info("True key ends with %s", api_key[-4:])
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
                logging.info("Starting server")
                bot.send_message(chat_id, f"Attempting to start server\\. Please wait")
                
                status = aws_utils.get_instance_status(region, instance_id).lower()
                if status == 'running':
                    logging.info("Could not start server: it's already running")
                    
                    public_ip = aws_utils.get_public_ip(region, instance_id)
                    bot.send_message(chat_id, f"Server is already running\\!\n" + 
                                    f"Use this IP to connect:\n||{utils.escape_string(public_ip)}||")
                    return
                
                if status == 'pending':
                    logging.info("Could not start server: it's pending")
                    
                    public_ip = aws_utils.get_public_ip(region, instance_id)
                    bot.send_message(chat_id, f"Server is starting\\!\n" + 
                                    f"Please wait")
                    return
                
                # Dont start server while in development
                if DEV == 0:
                    aws_utils.start_instance(region, instance_id)
                
                public_ip = aws_utils.get_public_ip(region, instance_id)
                if DEV == 1:
                    public_ip = '192.168.0.1'
                
                bot.send_message(chat_id, f"Instance started, starting Valheim dedicated server\nYou will be able to connect shortly\n" +
                                f"Use this IP to connect:\n||{utils.escape_string(public_ip)}||")
                
                logging.info("Server started successfully")
                
                # Notify the owner
                if chat_id != owner_id:
                    bot.send_message(owner_id, f"Server started by @{utils.escape_string(message['from']['username'])}\n")
            except ClientError as e:
                logging.error('An error occurred (%s): %s', str(e), e)
                bot.send_message(chat_id, "An error occured while starting the server")
            except Exception as e:
                logging.error('An error occurred (%s): %s', str(e), e)
            
        def stop_server(chat_id, message):
            try:
                logging.info("Stopping server")
                
                bot.send_message(chat_id, "Stopping server")
                
                if aws_utils.get_instance_status(region, instance_id).lower() == 'stopped':
                    bot.send_message(chat_id, f"Server is not running\\!\n")
                    return
                
                aws_utils.stop_instance(region, instance_id)
                bot.send_message(chat_id, "Server stopped")
                logging.info("Server stopped")
                
                # Notify the owner
                if chat_id != owner_id:
                    bot.send_message(owner_id, f"Server stopped by @{utils.escape_string(message['from']['username'])}\n")
            except ClientError as e:
                logging.error('An error occurred (%s): %s', str(e), e)
                bot.send_message(chat_id, "An error occured while stopping the server")
            except Exception as e:
                logging.error('An error occurred (%s): %s', str(e), e)
            
        def get_server_status(chat_id, message):
            try:
                logging.info("Retrieving server status")
                
                status = aws_utils.get_instance_status(region, instance_id)
                
                message = f"The server is {utils.escape_string(status)}\\.\n"   
                        
                if DEV == 1:
                    public_ip = '192.168.0.1'
                    message = message + f"Use ||{utils.escape_string(public_ip)}|| to connect\n"
                
                if status == 'running':
                    logging.info("The server is running, retrieving CPU data")
                    
                    public_ip = aws_utils.get_public_ip(region, instance_id)
                    message = message + f"Use ||{utils.escape_string(public_ip)}|| to connect\n"
                    
                    usage = aws_utils.get_instance_usage(region, instance_id)
                    # if one is None, the other one is None too
                    if usage['avg'] is not None:
                        message = message + f"CPU usage \\(peak\\): {utils.escape_string(str(round(usage['max'], 3)))}%\n"
                        message = message + f"CPU usage \\(average\\): {utils.escape_string(str(round(usage['avg'], 3)))}%\n"
                
                bot.send_message(chat_id, message)
            except ClientError as e:
                logging.error('An error occurred (%s): %s', str(e), e)
                bot.send_message(chat_id, "An error occured while retrieving server status")
            except Exception as e:
                logging.error('Unexpected error (%s): %s', str(e), e)
        
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
