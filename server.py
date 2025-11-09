import os
from google import genai
import json
from google.genai import types
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

# --- Gemini API Setup ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if api_key:
    print("API key loaded successfully.")
    client = genai.Client()
else:
    print("Error: GOOGLE_API_KEY not found in .env file.")
    client = None

# --- Configuration ---
# The server will look for this file in the same directory
CLEAN_REFERENCE_IMAGE_PATH = 'clean2.jpg' 
DATA_FILE = 'water_cooler_status.json'

# --- Load Hardcoded Clean Reference Image ---
CLEAN_REF_PART = None
if client: # Only try to load if client is initialized
    try:
        if not os.path.exists(CLEAN_REFERENCE_IMAGE_PATH):
            raise FileNotFoundError(f"'{CLEAN_REFERENCE_IMAGE_PATH}' not found. Please add this file to the server directory.")
        
        with open(CLEAN_REFERENCE_IMAGE_PATH, 'rb') as f:
            image_bytes = f.read()
        
        # Determine mime type from extension
        mime_type = 'image/jpeg' if CLEAN_REFERENCE_IMAGE_PATH.endswith('.jpg') or CLEAN_REFERENCE_IMAGE_PATH.endswith('.jpeg') else 'image/png'
        
        CLEAN_REF_PART = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        print(f"Successfully loaded hardcoded clean reference image from {CLEAN_REFERENCE_IMAGE_PATH}")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not load clean reference image: {e}")
        print("The application will not be able to perform comparisons.")

# --- Flask Server Setup ---
app = Flask(__name__)
CORS(app) 

# --- Data File Management ---
# ... (get_initial_data function is unchanged) ...
def get_initial_data():
    return {
        "cooler-1": {"name": "AB3-218", "status": "Unknown", "lastCleaningDate": None},
        "cooler-2": {"name": "Sports complex", "status": "Unknown", "lastCleaningDate": None},
        "cooler-3": {"name": "SPS 3", "status": "Unknown", "lastCleaningDate": None},
        "cooler-4": {"name": "Pragya Bhawan", "status": "Unknown", "lastCleaningDate": None},
        "cooler-5": {"name": "Hostel", "status": "Unknown", "lastCleaningDate": None},
    }

# ... (load_status_data function is unchanged) ...
def load_status_data():
    if not os.path.exists(DATA_FILE):
        print(f"Data file not found. Creating {DATA_FILE}...")
        with open(DATA_FILE, 'w') as f:
            json.dump(get_initial_data(), f, indent=4)
    
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            if not data or not isinstance(data, dict):
                raise ValueError("Data file is empty or corrupted.")
            return data
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error reading {DATA_FILE}: {e}. Re-initializing file.")
        with open(DATA_FILE, 'w') as f:
            json.dump(get_initial_data(), f, indent=4)
        return get_initial_data()

# ... (save_status_data function is unchanged) ...
def save_status_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"Error saving data to {DATA_FILE}: {e}")

# --- Helper Function to Call Gemini for Comparison (UPDATED) ---
def get_comparison_result(image_to_check_part, prompt):
    """
    Calls Gemini with the hardcoded reference image and an image to check.
    Returns 'CLEAN', 'NEEDS CLEANING', or 'UNKNOWN'.
    """
    if not client:
        raise Exception("Gemini client not initialized.")
    
    if not CLEAN_REF_PART: # Check if the global part loaded successfully
        raise Exception(f"Critical: Clean reference image '{CLEAN_REFERENCE_IMAGE_PATH}' is not loaded.")
        
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[prompt, CLEAN_REF_PART, image_to_check_part] # Use global CLEAN_REF_PART
        )
        
        text_response = response.text.strip().upper()
        print(f"Gemini Cleanliness raw response: {response.text}")

        if "NEEDS CLEANING" in text_response:
            return "NEEDS CLEANING"
        elif "CLEAN" in text_response:
            return "CLEAN"
        else:
            print(f"Warning: Unexpected Gemini Cleanliness response: {response.text}")
            return "UNKNOWN" 
            
    except Exception as e:
        print(f"Error during Gemini Cleanliness API call: {e}")
        raise Exception(f"Gemini API error: {e}")


# --- Helper Function for TDS Analysis (Unchanged) ---
def get_tds_result(tds_part):
    """
    Calls Gemini with a TDS image and a prompt.
    Returns 'SAFE', 'UNSAFE', or 'UNKNOWN'.
    """
    if not client:
        raise Exception("Gemini client not initialized.")
        
    try:
        # This prompt is specific to get a binary answer
        prompt = ("This is an image of a TDS (Total Dissolved Solids) meter. "
                  "Analyze the number. Is this reading safe for drinking water (e.g., generally below 300-500 ppm)? "
                  "Respond with only the single word 'SAFE' or 'UNSAFE'.")
                  
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=[prompt, tds_part]
        )
        
        text_response = response.text.strip().upper()
        print(f"Gemini TDS raw response: {response.text}")

        if "UNSAFE" in text_response:
            return "UNSAFE"
        elif "SAFE" in text_response:
            return "SAFE"
        else:
            print(f"Warning: Unexpected Gemini TDS response: {response.text}")
            return "UNKNOWN" 
            
    except Exception as e:
        print(f"Error during Gemini TDS API call: {e}")
        raise Exception(f"Gemini API error: {e}")


# --- Helper to create a 'Part' from a file (Unchanged) ---
def file_to_part(file_storage):
    """Converts a FileStorage object to a Gemini types.Part"""
    image_bytes = file_storage.read()
    mime_type = file_storage.mimetype or 'image/jpeg'
    return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

# --- API Endpoint 2: Get Live Status (Unchanged) ---
@app.route('/get-status', methods=['GET'])
def get_status():
    print("Loading status data for dashboard...")
    data = load_status_data()
    return jsonify(data)

# --- API Endpoint 3: Check 'Before' Image (UPDATED) ---
@app.route('/check-before-image', methods=['POST'])
def check_before_image():
    # Removed 'clean_reference_image' from check
    if 'before_image' not in request.files:
        return "Missing 'before_image'.", 400

    try:
        # Removed clean_ref_part creation
        before_part = file_to_part(request.files['before_image'])
        
        cooler_id = request.form.get('cooler_id', 'Unknown')
        print(f"Checking 'Before' image for cooler: {cooler_id}")
        
        prompt = ("Image 1 is a 'clean reference' water cooler. Image 2 is the 'before' image of a cooler to be checked. "
                  "Compare Image 2 to Image 1. Does Image 2 look dirty or like it needs cleaning? "
                  "Respond with only the words 'CLEAN' or 'NEEDS CLEANING'.")

        analysis_result = get_comparison_result(before_part, prompt) # Updated call
        
        print(f"Gemini 'Before' analysis: {analysis_result}")
        if analysis_result == "UNKNOWN":
             return "Analysis Inconclusive: Could not determine cleanliness. Please try a clearer reference image.", 400
             
        return analysis_result
        
    except Exception as e:
        return str(e), 500

# --- API Endpoint 4: Submit Final Cleaning Report (UPDATED) ---
@app.route('/submit-cleaning-report', methods=['POST'])
def submit_cleaning_report():
    # Removed 'clean_reference_image' from check
    if 'after_image' not in request.files or 'tds_image' not in request.files or 'cooler_id' not in request.form:
        return "Missing 'after_image', 'tds_image', or 'cooler_id'.", 400

    cooler_id = request.form['cooler_id']

    try:
        # --- 1. Create 'Parts' from all files ---
        # Removed clean_ref_part creation
        after_part = file_to_part(request.files['after_image'])
        tds_part = file_to_part(request.files['tds_image'])
        
        print(f"Checking Final Report for cooler: {cooler_id}")
        
        # --- 2. Check Tank Cleanliness ---
        cleanliness_prompt = ("Image 1 is a 'clean reference' water cooler. Image 2 is the 'after' image from a cleaning job. "
                              "Does Image 2 look as clean as Image 1? "
                              "Respond with only the words 'CLEAN' or 'NEEDS CLEANING'.")
        analysis_result_cleanliness = get_comparison_result(after_part, cleanliness_prompt) # Updated call
        print(f"Gemini 'After' analysis: {analysis_result_cleanliness}")

        # --- 3. Check TDS Safety ---
        analysis_result_tds = get_tds_result(tds_part)
        print(f"Gemini 'TDS' analysis: {analysis_result_tds}")
        
        # --- 4. Final Logic Check ---
        is_clean = analysis_result_cleanliness == "CLEAN"
        is_safe = analysis_result_tds == "SAFE"

        if is_clean and is_safe:
            # SUCCESS: Update status file
            print(f"SUCCESS: Report for {cooler_id} is CLEAN and SAFE. Updating status file.")
            data = load_status_data()
            if cooler_id in data:
                data[cooler_id]['status'] = 'Clean' 
                data[cooler_id]['lastCleaningDate'] = datetime.now().isoformat()
                save_status_data(data)
                return f"Report OK: Tank is CLEAN and TDS is SAFE. Status for {data[cooler_id]['name']} has been updated.", 200
            else:
                return f"Error: Cooler ID {cooler_id} not found in database.", 404
        else:
            # FAILURE: Build a detailed error message
            errors = []
            if not is_clean:
                errors.append(f"Tank still looks {analysis_result_cleanliness}")
            if not is_safe:
                errors.append(f"TDS is {analysis_result_tds}")
            
            error_msg = "Report FAILED: " + ", ".join(errors) + ". Please fix the issues and resubmit."
            print(f"FAILED: {error_msg}")
            return error_msg, 400
            
    except Exception as e:
        return str(e), 500

# --- Run the Server ---
if __name__ == '__main__':
    print("Starting Flask server at http://localhost:5000")
    print(f"Data will be stored in {os.path.abspath(DATA_FILE)}")
    app.run(debug=True, port=5000)