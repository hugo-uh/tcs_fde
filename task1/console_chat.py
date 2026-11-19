import os
import dotenv
import boto3 

dotenv.load_dotenv("../.env")

client = boto3.client('bedrock-runtime')
messages = []

while True:
    inputMessage = input("$: ")

    if inputMessage in ["exit", "quit"]:
        print("Good bye!")
        exit()

    message = {
        "role": "user",
        "content": [{"text": inputMessage}]
    }
    messages.append(message)
    response = client.converse(
        modelId=os.environ.get("MODEL_ID"),
        messages=messages,
        inferenceConfig={
            "maxTokens": 500,
            "temperature": 0.5
        }
    )
    messages.append(response['output']['message'])
    print(response['output']['message']['content'][0]['text'] + "\n")
