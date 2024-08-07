from flask import Flask, request, jsonify, abort
import json
import os
import logging
import requests
from dotenv import load_dotenv
app = Flask(__name__)
load_dotenv()
# Configure logging
logging.basicConfig(level=logging.INFO)

# Secret key for authentication
SERVER_SECRET = "s3cr3tK3yExAmpl3SecReT"



DEFAULT_COMPANY = os.getenv('DEFAULT_COMPANY')

API_BASE_URL = os.getenv('API_BASE_URL')
DB_BASE_URL = os.getenv('DB_BASE_URL')


def search_person(full_name, company=DEFAULT_COMPANY):
    base_url = DB_BASE_URL
    search_url = f"{base_url}/api/company-structure/{company}"
    
    try:
        response = requests.get(search_url)
        response.raise_for_status()
        
        company_data = response.json()
        
        for company_name, organizations in company_data.items():
            for org_name, people in organizations.items():
                for person in people:
                    if f"{person.get('firstname', '')} {person.get('lastname', '')}".strip().lower() == full_name.lower():
                        return {
                            "found": True,
                            "personId": person.get("personid"),
                            "concernId": person.get("concerned"),
                            "phoneNumber": person.get("phoneNumbers", [])[0] if person.get("phoneNumbers") else None,
                            "fullName": f"{person.get('firstname', '')} {person.get('lastname', '')}".strip()
                        }
        
        return {"found": False, "message": f"No person found with the name '{full_name}' in company '{company}'"}
    
    except requests.exceptions.RequestException as e:
        return {"error": "api_error", "message": f"Error occurred while searching for '{full_name}': {str(e)}"}

def check_calendar(concern_id, person_id):
    if not concern_id or not person_id:
        logging.warning("check_calendar called with missing concernId or personId")
        return {"error": "Missing concernId or personId"}
    
    logging.info(f"Checking calendar for concern_id: {concern_id}, person_id: {person_id}")
    
    url = f"{API_BASE_URL}/check_person_status/{concern_id}/{person_id}"
    logging.debug(f"Constructed URL: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        logging.debug(f"Received response with status: {response.status_code}")
        logging.debug(f"Response body: {response.text}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                logging.info(f"Calendar check result: {json.dumps(data, indent=2)}")
                
                if data.get('success', False):
                    content = json.loads(data.get('content', '{}'))
                    status = content.get('data', {}).get('status', 'unknown')
                    
                    logging.info(f"Person availability status: {status}")
                    
                    result = {
                        "available": status == 'available',
                        "status": status,
                        "details": content
                    }
                    logging.info(f"Final calendar check result: {json.dumps(result, indent=2)}")
                    return result
                else:
                    error_message = "API request was not successful"
                    logging.error(error_message)
                    return {"error": error_message, "status": "error"}
            except json.JSONDecodeError:
                logging.error(f"Failed to parse JSON response: {response.text}")
                return {"error": "Failed to parse API response", "status": "error"}
        else:
            error_msg = f"Failed to check availability. Status: {response.status_code}"
            logging.warning(error_msg)
            return {"error": error_msg, "status": "error"}
    except requests.RequestException as e:
        error_msg = f"Error checking availability: {str(e)}"
        logging.error(error_msg)
        return {"error": error_msg, "status": "error"}

# def check_calendar(concern_id, person_id):
#     # Simulate a successful calendar check for testing purposes
#     return {
#         "available": True,
#         "status": "available",
#         "details": {"data": {"status": "available"}}
#     }

# Corrected availability data
# availability_data = {
#     "Markus Salminen": {"found": True, "available": True, "status": "available"},
#     "John Doe": {"found": True, "available": True, "status": "available"},
#     "Jane Scotson": {"found": True, "available": True, "status": "available"},
#     "Pops Apell": {"found": True, "available": True, "status": "available"},
#     "Jari Moilanen": {"found": True, "available": True, "status": "available"}
# }

@app.route('/handle_call', methods=['POST'])
def handle_incoming_call():
    app.logger.info("Received request at /handle_call")
    data = request.json
    app.logger.info(f"Incoming Request Data: {json.dumps(data, indent=2)}")
    app.logger.info(f"Headers: {dict(request.headers)}")

    received_secret = request.headers.get('X-Vapi-Secret')
    app.logger.info(f"Received Secret: {'*' * len(received_secret) if received_secret else 'None'}")

    if received_secret != SERVER_SECRET:
        app.logger.warning("Secret mismatch. Access denied.")
        abort(403)

    message_type = data.get('message', {}).get('type')
    app.logger.info(f"Message Type: {message_type}")

    if message_type == 'assistant-request':
        app.logger.info("Handling assistant-request")
        response = {
            "assistant": {
                "firstMessage": "Hello! I'm your availability assistant. How can I help you today?",
                "model": {
                    "provider": "openai",
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "system",
                            "content": """You are a helpful availability assistant. When a user asks about the availability of a specific person, use the check_availability function to retrieve the current availability information.

List of names:
1. Markus Salminen
2. John Doe
3. Jane Scotson
4. Pops Apell
5. Jari Moilanen

Name Matching Process:
1. When a user mentions a name, check if it exactly matches one of the names in the list above. if the person says, number 5 from your list meaning the list of names.
2. If there's an exact match, immediately use the check_availability function with that name.
3. If there isn't an exact match, but the name is similar to one in the list, ask the user: "Do you mean [closest matching name from the list]?"
4. If the user confirms, use the check_availability function with the confirmed name.
5. If the user doesn't confirm or no similar name is found, apologize and ask if they'd like to try another name.
6. Always use the exact spelling from the list when calling the check_availability function.

Remember, only call the check_availability function when you have an exact match from the list above.
Remember, only call the check_availability function when you have an exact match from the list above.

After checking availability:
1. If the person is available:
   a) Inform the user that the person is available.
   b) Ask if they would like to be connected.
   c) If the user agrees, use the transferCall function with the number +358468422410.
   d) If the user declines, ask if they'd like to check another person's availability.
2. If the person is not available:
   a) Inform the user that the person is not available.
   b) Ask if they would like to check another person's availability.

Important:
- Only use the transferCall function when a specific person has been requested, confirmed to be available, and the user has agreed to be connected.
- The transferCall function should be used with the phone number +358468422410 for all transfers.
- Do not offer to transfer the call unless you've confirmed the person's availability first.
"""
                        }
                    ],
                    "functions": [
                        {
                            "name": "check_availability",
                            "description": "Checks the availability for a specified person",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "fullName": {"type": "string", "description": "The full name of the person to check availability for, exactly as it appears in the list"}
                                },
                                "required": ["fullName"]
                            }
                        },
                        {
                            "name": "transferCall",
                            "description": "Use this function to transfer the call when the person is available and the user wants to be connected.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "destination": {
                                        "type": "string",
                                        "enum": ["+358468422410","+358468422410","+358468422410"],
                                        "description": "The phone number to transfer the call to."
                                    }
                                },
                                "required": [
                                    "destination"
                                ]
                            }
                        }
                    ],
                    "messages": [
                        {
                            "type": "request-start",
                            "content": "I am forwarding your call. Please stay on the line.",
                            "conditions": [
                                {
                                    "param": "destination",
                                    "operator": "eq",
                                    "value": "+358468422410"
                                }
                            ]
                        }
                    ]
                }
            }
        }
        
        app.logger.info("Sending assistant-request response")
        return jsonify(response), 200

    elif message_type == 'function-call':
        app.logger.info("Handling function-call")
        function_call = data.get('message', {}).get('functionCall', {})
        function_name = function_call.get('name')
        parameters = function_call.get('parameters')
        app.logger.info(f"Function Name: {function_name}")
        app.logger.info(f"Parameters: {json.dumps(parameters, indent=2)}")

        if function_name == 'check_availability':
            full_name = parameters.get('fullName')
            if full_name:
                person_data = search_person(full_name)
                if person_data.get("found"):
                    calendar_result = check_calendar(person_data["concernId"], person_data["personId"])
                    
                    # Extract the availability status from the calendar result
                    is_available = calendar_result.get("available", False)
                    status = calendar_result.get("status", "unknown")
                    
                    result = {
                        "found": True,
                        "fullName": person_data["fullName"],
                        "available": is_available,
                        "status": status,
                        "phoneNumber": person_data["phoneNumber"]
                    }
                else:
                    result = {"found": False, "message": person_data.get("message", "Person not found in database")}
                return jsonify({"content": json.dumps(result)}), 200
            else:
                app.logger.error("Full name not provided in parameters")
                return jsonify({"error": "Full name not provided"}), 400
        else:
            app.logger.warning(f"Unknown function name: {function_name}")
            return jsonify({"error": f"Unknown function: {function_name}"}), 400

    else:
        app.logger.warning(f"Invalid request type: {message_type}")
        return jsonify({"error": "Invalid request"}), 400
    

if __name__ == '__main__':
    app.run(debug=True)



    