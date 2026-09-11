from flask import Flask, request, render_template, jsonify
import json, jwt
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

app = Flask(__name__)

@app.route('/', methods=['GET'])
def sample():
    return render_template('home.html')


@app.route('/token', methods=['POST'])
def token():
    """
    Token generation endpoint.
    
    NOTE: For production use, make sure to handle actual verification of userid
    and password against a secure database or authentication service before
    generating and returning the token. This demo implementation does not
    perform real authentication checks.
    """
    data = request.get_json() or {}
    user_id = data.get('userid', None)
    password = data.get('password', None)

    if user_id is None:
        return "userid is required", 403
    
    if password is None:
        return "password is required", 403
    
    # TODO: Add actual authentication verification here for production
    # Example: Verify userid and password against database
    # if not verify_credentials(user_id, password):
    #     return "Invalid credentials", 401

    # In below, user_id is context variable, which will be extracted by watsonx Orchestrate tool during runtime.
    context = {
        "user_id": user_id
    }
        
    sub = context["user_id"]

    user_payload = {
        "custom_message": "Here is the custom message",
        "name": "John",
    }

    data_bytes = json.dumps(user_payload).encode("utf-8")

    with open("./secrets/public_key.pem", "rb") as f:
      PUBLIC_KEY = serialization.load_pem_public_key(f.read())


    with open('./secrets/private_key.pem', 'r') as f:
      PRIVATE_KEY = f.read()


    encrypted_payload = PUBLIC_KEY.encrypt(
        data_bytes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    jwt_content = {
        "sub": sub,
        "user_payload": encrypted_payload.hex(),
        "context": context,
        "exp": datetime.now() + timedelta(minutes=60),
    }

    token = jwt.encode(
        jwt_content,
        PRIVATE_KEY,
        algorithm="RS256"
    )

    return token


@app.route('/data', methods=['GET'])
def get_data():

    user_id = request.args.get('user_id')

    """
    Profile data endpoint.
    
    NOTE: For production use, make sure to validate the userid and token
    before returning any data. This demo implementation does not perform
    authentication/authorization checks.
    
    TODO: Add authentication and authorization here for production
    Example:
    - Extract token from Authorization header
    - Verify token signature and expiration
    - Extract userid from token claims
    - Verify user has permission to access this data
    - Return data specific to the authenticated user
    """
    # TODO: Implement token validation
    # token = request.headers.get('Authorization', '').replace('Bearer ', '')
    # if not token:
    #     return jsonify({"error": "Token required"}), 401
    #
    # try:
    #     decoded = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
    #     user_id = decoded.get('sub')
    # except jwt.InvalidTokenError:
    #     return jsonify({"error": "Invalid token"}), 401
    
    profile_data = {
        "User ID": "1",
        "Username": "alexrivera",
        "Full Name": "Alex Rivera",
        "Email": "alex.rivera@example.com",
        "Phone": "+1-555-274-8392",
        "Job Title": "Product Designer",
        "Company": "BrightLabs",
        "Date of Birth": "1994-08-17",
        "Bio": "Designer focused on creating intuitive digital experiences. Coffee enthusiast and weekend hiker.",
        "Interests": "Design, Technology, Travel, Photography",
        "Address": "742 Evergreen Terrace, Springfield, IL 62704, USA",
        "Created At": "2026-02-16 10:22 UTC",
        "Social Media": {
            "GitHub": "github.com/alexrivera",
            "LinkedIn": "linkedin.com/in/alexrivera",
            "Twitter": "@alexrivera"
        }
    }
    
    return jsonify(profile_data)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

