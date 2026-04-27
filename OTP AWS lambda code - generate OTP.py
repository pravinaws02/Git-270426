import boto3
import os
import json
import random
import time
import hashlib
import hmac
import secrets

dynamodb = boto3.client('dynamodb')
sns = boto3.client('sns')

OTP_TABLE = os.environ['OTP_TABLE']
OTP_TTL_SECONDS = int(os.environ.get('OTP_TTL_SECONDS', 300))  # 5 minutes default


def generate_otp():
    return str(random.randint(100000, 999999))


def hash_otp(otp, salt):
    """Hash OTP using SHA256 with salt."""
    return hmac.new(salt.encode(), otp.encode(), hashlib.sha256).hexdigest()


def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
        phone_number = body.get('phoneNumber')

        if not phone_number:
            return {"statusCode": 400, "body": json.dumps({"error": "phoneNumber required"})}

        # Generate OTP and salt
        otp = generate_otp()
        salt = secrets.token_hex(8)
        otp_hash = hash_otp(otp, salt)
        expires_at = int(time.time()) + OTP_TTL_SECONDS

        # Store in DynamoDB
        dynamodb.put_item(
            TableName=OTP_TABLE,
            Item={
                'phoneNumber': {'S': phone_number},
                'otpHash': {'S': otp_hash},
                'salt': {'S': salt},
                'expiresAt': {'N': str(expires_at)},
                'attempts': {'N': '0'}
            }
        )

        # Send SMS using SNS
        message = f"Your verification code is {otp}. It will expire in {OTP_TTL_SECONDS//60} minutes."
        sns.publish(PhoneNumber=phone_number, Message=message)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "OTP sent successfully"})
        }

    except Exception as e:
        print(f"Error generating OTP: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"})
        }
