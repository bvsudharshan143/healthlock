import os
import json
import logging
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fallback dummy data
DUMMY_DATA = {
    "analysis": "Treatment A",
    "result": 0.045,
    "description": "Recovery improvement rate"
}

def get_boto3_client(service_name):
    """
    Helper function to initialize a boto3 client if AWS credentials are set.
    """
    try:
        # Boto3 automatically checks environment variables AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
        # But we can enforce a check to avoid hanging or slow fallback if not intended.
        if os.environ.get('AWS_ACCESS_KEY_ID') and os.environ.get('AWS_SECRET_ACCESS_KEY'):
            return boto3.client(
                service_name,
                region_name=os.environ.get('AWS_REGION', 'us-east-1')
            )
        return None
    except Exception as e:
        logger.error(f"Error creating client for {service_name}: {e}")
        return None

def get_analysis_data(analysis_type):
    """
    Simulates a federated query or retrieves results from an S3 bucket.
    """
    s3 = get_boto3_client('s3')
    bucket_name = os.environ.get('S3_BUCKET_NAME', 'healthlock-output-bucket')
    
    if s3:
        try:
            # Assuming files are named after the analysis type (e.g., drug_effectiveness.json)
            file_key = f"{analysis_type.lower().replace(' ', '_')}.json"
            response = s3.get_object(Bucket=bucket_name, Key=file_key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            logger.info(f"Successfully fetched data from S3 for {analysis_type}")
            return data
        except ClientError as e:
            logger.warning(f"Failed to fetch from S3 ({e.response['Error']['Code']}), falling back to dummy data.")
        except Exception as e:
            logger.warning(f"Error reading from S3, falling back to dummy data. Error: {e}")
            
    # Fallback to dummy data based on analysis type
    logger.info("Using simulated data for federated query.")
    if analysis_type == "Drug Effectiveness":
        return {"analysis": "Treatment A", "result": 0.045, "description": "Recovery improvement rate"}
    elif analysis_type == "Patient Recovery Rate":
        return {"analysis": "Physical Therapy", "result": 0.12, "description": "Speed of recovery"}
    elif analysis_type == "Side Effects Detection":
        return {"analysis": "Medication B", "result": 0.02, "description": "Incidence of nausea"}
    
    return DUMMY_DATA

def generate_ai_summary(data):
    """
    Uses Amazon Bedrock (Nova Lite model) to convert statistical data into human-readable insights.
    """
    bedrock = get_boto3_client('bedrock-runtime')
    
    prompt = f"Convert this medical statistical result into a human-readable insight: {data.get('result')} {data.get('description')} for {data.get('analysis')}."
    
    if bedrock:
        try:
            # Using Amazon Nova Lite model via the recommended Converse API
            model_id = "us.amazon.nova-lite-v1:0"
            
            messages = [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ]
            
            response = bedrock.converse(
                modelId=model_id,
                messages=messages,
                inferenceConfig={"temperature": 0.7, "maxTokens": 200}
            )
            
            insight = response['output']['message']['content'][0]['text']
            logger.info("Successfully generated AI insight using Amazon Bedrock.")
            return insight
        except Exception as e:
            logger.warning(f"Bedrock invocation failed, using fallback summary. Error: {e}")
            
    # Fallback response if Bedrock isn't configured or fails
    logger.info("Using fallback AI summary.")
    return f"The federated analysis indicates a {data.get('result') * 100:.1f}% {data.get('description')} associated with {data.get('analysis')}."
