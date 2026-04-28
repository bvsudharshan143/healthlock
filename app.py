from flask import Flask, render_template, request
import boto3
import json

app = Flask(__name__)

# =========================
# CONFIGURATION
# =========================
BUCKET_NAME = "healthlock-output-bucket"
FILE_KEY = "output.json"
REGION = "ap-south-1"

# AWS Clients
s3 = boto3.client('s3', region_name=REGION)
bedrock = boto3.client('bedrock-runtime', region_name=REGION)

# =========================
# FUNCTION: FETCH DATA FROM S3
# =========================
def get_analysis_data():
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=FILE_KEY)
        content = response['Body'].read().decode('utf-8')
        data = json.loads(content)
        return data
    except Exception as e:
        print("S3 Error:", e)

        # Fallback data (VERY IMPORTANT FOR DEMO)
        return {
            "analysis": "Treatment A",
            "result": 0.045,
            "description": "Recovery improvement rate (fallback)"
        }

# =========================
# FUNCTION: GENERATE AI SUMMARY (BEDROCK)
# =========================
def generate_ai_summary(data):
    try:
        value = data["result"]
        treatment = data["analysis"]

        prompt = f"""
        You are a medical analyst.
        Convert this statistical result into a simple insight.

        Treatment: {treatment}
        Improvement Value: {value}

        Give a clear, professional explanation in 2-3 lines.
        """

        body = {
            "inputText": prompt
        }

        response = bedrock.invoke_model(
            modelId="amazon.nova-lite-v1",
            body=json.dumps(body)
        )

        result = json.loads(response['body'].read())

        return result.get("outputText", "No AI response generated.")

    except Exception as e:
        print("Bedrock Error:", e)

        # Fallback AI response (VERY IMPORTANT)
        return f"Estimated insight: {data['result']*100}% improvement observed in patients using {data['analysis']}."

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_analysis():
    data = run_athena_query()
    insight = generate_ai_summary(data)

    return render_template("result.html", data=data, insight=insight)

def run_athena_query():
    import time
    import csv
    
    try:
        athena = boto3.client('athena', region_name='ap-south-1')

        query = """
        SELECT treatment, AVG(recovery_rate) AS avg_recovery
        FROM patient_data
        GROUP BY treatment
        """

        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': 'healthlock_db'},
            ResultConfiguration={
                'OutputLocation': 's3://healthlock-athena-output/'
            }
        )

        query_execution_id = response['QueryExecutionId']

        # Wait for query to complete
        while True:
            status = athena.get_query_execution(QueryExecutionId=query_execution_id)
            state = status['QueryExecution']['Status']['State']

            if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            time.sleep(2)

        result = athena.get_query_results(QueryExecutionId=query_execution_id)

        rows = result['ResultSet']['Rows']

        # Skip header
        data = rows[1]['Data']

        return {
            "analysis": data[0]['VarCharValue'],
            "result": float(data[1]['VarCharValue']),
            "description": "Average recovery rate from Athena"
        }
    except Exception as e:
        print(f"Athena Query Failed ({e}), falling back to local CSV simulation.")
        try:
            with open('patient_data.csv', 'r') as f:
                reader = csv.DictReader(f)
                treatment_a_rates = []
                for row in reader:
                    if row['treatment'] == 'Treatment A':
                        treatment_a_rates.append(float(row['recovery_rate']))
                
                avg_rate = sum(treatment_a_rates) / len(treatment_a_rates) if treatment_a_rates else 0.045
                
                return {
                    "analysis": "Treatment A",
                    "result": avg_rate,
                    "description": "Average recovery rate (Local Simulation)"
                }
        except Exception as e2:
            print("Local CSV read failed:", e2)
            return {
                "analysis": "Treatment A",
                "result": 0.045,
                "description": "Average recovery rate (Fallback)"
            }
# =========================
# RUN APP
# =========================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
