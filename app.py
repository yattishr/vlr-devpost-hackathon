from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, jsonify
import boto3
import json
import inspect
from botocore.exceptions import ParamValidationError, ClientError

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Initialize the Bedrock Runtime client
bedrock_runtime = boto3.client(
    service_name='bedrock-agent-runtime',
    region_name=os.getenv('AWS_DEFAULT_REGION')
)

AGENT_ID = os.getenv('AGENT_ID')
AGENT_ALIAS_ID = os.getenv('AGENT_ALIAS_ID')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json['message']
    
    try:
        # Print the method signature
        print("Method signature:", inspect.signature(bedrock_runtime.invoke_agent))
        
        # Prepare the parameters
        params = {
            "agentId": AGENT_ID,
            "agentAliasId": AGENT_ALIAS_ID,
            "sessionId": 'user-session-id',
            "inputText": user_message
        }
        
        # Print the parameters we're about to use
        print("Invoking with parameters:", params)

        # Invoke the agent
        response = bedrock_runtime.invoke_agent(**params)

        # Process the EventStream response
        full_response = ""
        for event in response['completion']:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    full_response += chunk['bytes'].decode('utf-8')

        return jsonify({'response': full_response})

    except ParamValidationError as e:
        print(f"Parameter validation error: {str(e)}")
        return jsonify({'response': "Sorry, there was an error with the request parameters."}), 400
    except ClientError as e:
        print(f"Error invoking agent: {str(e)}")
        return jsonify({'response': "Sorry, I encountered an error while processing your request."}), 500

if __name__ == '__main__':
    app.run(debug=True)