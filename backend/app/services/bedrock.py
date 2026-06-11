import os
import boto3
import json

client=boto3.client("bedrock",region_name=os.getenv("AWS_REGION", "ap-south-1"))

def call_bedrock_api(note_text: str) -> dict:
    response = client.invoke_model(
        modelId=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-2"),
        contentType="application/json",
        body=json.dumps({"input": note_text}),
        accept="application/json",
    )
    return json.loads(response["body"].read())