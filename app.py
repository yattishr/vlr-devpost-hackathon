from flask import Flask, render_template, request, jsonify
import boto3
import json
import inspect
from botocore.exceptions import ParamValidationError, ClientError
from typing import Dict, Optional
import os

class SecretsManager:
    def __init__(self, secret_name: str, region_name: str = "us-east-1"):
        self.secret_name = secret_name
        self.region_name = region_name
        self.session = boto3.session.Session()
        self.client = self.session.client(
            service_name='secretsmanager',
            region_name=self.region_name
        )
        self._secrets_cache: Optional[Dict] = None

    def get_secret(self) -> Dict:
        """Retrieve and parse secrets from AWS Secrets Manager."""
        if self._secrets_cache is not None:
            return self._secrets_cache

        try:
            get_secret_value_response = self.client.get_secret_value(
                SecretId=self.secret_name
            )
            secret_string = get_secret_value_response['SecretString']
            self._secrets_cache = json.loads(secret_string)
            return self._secrets_cache
        except ClientError as e:
            print(f"Error retrieving secret: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            print(f"Error parsing secret JSON: {str(e)}")
            raise

app = Flask(__name__)

# Constants
AGENT_ID = 'EZSFAF10XH'
AGENT_ALIAS_ID = 'HF1GHAQSWJ'
AWS_DEFAULT_REGION = 'us-east-1'

def initialize_bedrock_client(secrets: Dict) -> boto3.client:
    """Initialize the Bedrock Runtime client with credentials from Secrets Manager"""
    return boto3.client(
        service_name='bedrock-agent-runtime',
        aws_access_key_id=secrets.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=secrets.get('AWS_SECRET_ACCESS_KEY'),
        region_name=AWS_DEFAULT_REGION
    )

def get_credentials():
    """Get credentials from either Secrets Manager or environment variables"""
    if os.getenv('AWS_EXECUTION_ENV'):  # Running in AWS
        try:
            secrets_manager = SecretsManager(
                secret_name="valorant-devpost-hackathon",
                region_name="us-east-1"
            )
            return secrets_manager.get_secret()
        except Exception as e:
            print(f"Error getting secrets: {str(e)}")
            raise
    else:  # Local development
        from dotenv import load_dotenv
        load_dotenv()
        return {
            'AWS_ACCESS_KEY_ID': os.getenv('AWS_ACCESS_KEY_ID'),
            'AWS_SECRET_ACCESS_KEY': os.getenv('AWS_SECRET_ACCESS_KEY')
        }

# Initialize credentials and bedrock client
try:
    credentials = get_credentials()
    bedrock_runtime = initialize_bedrock_client(credentials)
except Exception as e:
    print(f"Failed to initialize application: {str(e)}")
    raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json['message']
    
    try:
        # Print the method signature for debugging
        print("Method signature:", inspect.signature(bedrock_runtime.invoke_agent))
        
        # Prepare the parameters
        params = {
            "agentId": AGENT_ID,
            "agentAliasId": AGENT_ALIAS_ID,
            "sessionId": 'user-session-id',
            "inputText": user_message
        }
        
        # Print the parameters for debugging
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
        return jsonify({
            'response': "Sorry, there was an error with the request parameters.",
            'error': str(e)
        }), 400
    except ClientError as e:
        print(f"Error invoking agent: {str(e)}")
        return jsonify({
            'response': "Sorry, I encountered an error while processing your request.",
            'error': str(e)
        }), 500
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({
            'response': "An unexpected error occurred.",
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)