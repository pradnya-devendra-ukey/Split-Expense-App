import json
import re
from google import genai
from google.genai import types
from app.config import settings

def parse_receipt_with_gemini(image_bytes: bytes, mime_type: str = "image/jpeg"):
    api_key = (settings.GEMINI_API_KEY or "").strip()
    
    if not api_key or api_key in ["your_gemini_api_key_here", "your_actual_gemini_api_key_here"]:
        raise ValueError(
            "GEMINI_API_KEY is not configured or still has a placeholder value in your .env file. "
            "Please paste your real API key into .env (line 2)."
        )

    client = genai.Client(api_key=api_key)

    prompt = """
    Extract details from this receipt image. 
    Return a single JSON object with these exact keys:
    {
      "store_name": "Store Name",
      "total_amount": 0.00,
      "items": [
        {"item_name": "Item 1", "price": 0.00}
      ]
    }
    All prices and totals must be numbers (floats).
    """

    try:
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
        except Exception:
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

        raw_text = response.text.strip()
        
        # Fallback regex extraction if text surrounds the JSON
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group(0)

        data = json.loads(raw_text)

        # Apply default fallbacks for missing fields
        if not isinstance(data, dict):
            data = {"items": data if isinstance(data, list) else []}

        data.setdefault("store_name", "Store Receipt")
        data.setdefault("items", [])
        
        if "total_amount" not in data or not data["total_amount"]:
            data["total_amount"] = sum(float(item.get("price", 0.0)) for item in data["items"])

        return data

    except Exception as e:
        raise RuntimeError(f"Gemini processing error: {str(e)}")