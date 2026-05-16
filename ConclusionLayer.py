# Zyad Notes:
# - Passing you relevant extracted content from the website, along with the top coordinate guesses (which include the generalized location)
# - Gemini should produce a report that cross references the content with the location guesses to create a new guess with some confidence X
# - Read app.py to see what you should be returning for Rishi
"""
   The Conclusion Layer receives:
      - relevant_content  : str  — geo-relevant text extracted by AggregationLayer
      - gps_guesses       : dict — top coordinate guesses from GeoClip (AggregationLayer.infer_geolocation)
      - metadata          : dict — EXIF metadata pulled from ExtractionLayer (may be empty)
      - image_path        : str  — path to the scraped image on disk
 
    It passes all of these, plus the raw image, to Gemini, which produces:
      1. A ranked list of GPS coordinate guesses, each with a confidence value (0–1)
      2. A written report explaining the reasoning and any conflicts between sources
      3. A "key information" summary (people, places, events) for the PDF
"""
 
import os
import base64
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
 
 
class ConclusionLayer:
    def __init__(self):
        load_dotenv()
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = "gemini-2.5-flash"
 
    # Internal helpers 
    def _encode_image(self, image_path: str) -> tuple[str, str]:
        """
        Base64-encode the image so Gemini can see it directly.
        Returns (base64_data, mime_type).
        """
        ext = os.path.splitext(image_path)[-1].lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/jpeg")
 
        with open(image_path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode("utf-8")
 
        return b64, mime_type
 
    def _build_prompt(
        self,
        relevant_content: str,
        gps_guesses: dict,
        metadata: dict,
    ) -> str:
        """
        Construct the full text prompt that accompanies the image.
        """
        # Format GeoClip guesses into a readable block
        guesses_text = ""
        for rank, info in gps_guesses.items():
            guesses_text += (
                f"  Guess #{rank}: {info['Address']} "
                f"| Coords: {info['Prediction']} "
                f"| GeoClip Score: {info['Score']:.4f}\n"
            )
 
        # Format metadata (may be an empty dict if image had none)
        metadata_text = ""
        if metadata:
            for k, v in metadata.items():
                metadata_text += f"  {k}: {v}\n"
        else:
            metadata_text = "  No metadata available.\n"
 
        prompt = f"""
        You are an expert OSINT geolocation analyst. Your job is to synthesize multiple data sources to produce the most accurate location estimate possible.
         
        You have been given:
        1. An image (see attached)
        2. Relevant text content extracted from the webpage where the image was found
        3. Top GPS coordinate guesses from the GeoClip machine learning model
        4. EXIF metadata extracted from the image (if any)
         
        ---
         
        RELEVANT WEBPAGE CONTENT:
        {relevant_content if relevant_content.strip() else "No relevant content extracted."}
         
        ---
         
        GEOCLIP TOP GUESSES:
        {guesses_text if guesses_text.strip() else "No GeoClip guesses available."}
         
        ---
         
        IMAGE METADATA:
        {metadata_text}
         
        ---
         
        INSTRUCTIONS:
        Using all of the above (including your own visual analysis of the image), produce a JSON response with EXACTLY the following structure:
         
        {{
          "location_guesses": [
            {{
              "rank": 1,
              "location_name": "City, Region, Country",
              "coordinates": [latitude, longitude],
              "confidence": 0.XX,
              "reasoning": "Why you believe this is the correct location, citing specific signals from the image, content, metadata, or GeoClip"
            }},
            ...
          ],
          "conflict_analysis": "Describe any disagreements between data sources (e.g. metadata says Paris but GeoClip says Tokyo). If no conflicts, state 'No conflicts detected.'",
          "key_information": {{
            "best_guess": "Your single best location estimate as a plain string",
            "key_people": ["List any named individuals tied to this location, or empty list"],
            "key_places": ["Named places, landmarks, or regions identified"],
            "key_events": ["Events, dates, or occurrences tied to the location, or empty list"],
            "confidence_summary": "A one-sentence plain-English summary of your overall confidence and why"
          }},
          "full_report": "A 2–4 paragraph prose report suitable for an OSINT analyst. Cover: what visual signals in the image indicate location, how the webpage content supports or contradicts the GeoClip guesses, whether the metadata is consistent, your final recommended location and why, and any caveats."
        }}
         
        IMPORTANT:
        - confidence values must be between 0.0 and 1.0
        - Rank location_guesses from most to least confident
        - Provide at least 1 and at most 5 location_guesses
        - Return ONLY valid JSON. No markdown fences, no preamble.
        """
        return prompt
 
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
 
    def generate_report(
        self,
        relevant_content: str,
        gps_guesses: dict,
        metadata: dict,
        image_path: str,
    ) -> dict:
        """
        Main entry point. Call this from main.py after the aggregation layer runs.
 
        Parameters
        ----------
        relevant_content : str
            Geo-relevant text returned by AggregationLayer.extract_relevant_page_content()
        gps_guesses : dict
            Ranked guesses returned by AggregationLayer.infer_geolocation()
            Format: {1: {"Address": ..., "Prediction": (lat, lon), "Score": ...}, ...}
        metadata : dict
            EXIF/metadata dict from ExtractionLayer (can be empty)
        image_path : str
            Absolute or relative path to the saved image file
 
        Returns
        -------
        dict with keys:
            "location_guesses"  — list of ranked dicts (location_name, coordinates, confidence, reasoning)
            "conflict_analysis" — str
            "key_information"   — dict (best_guess, key_people, key_places, key_events, confidence_summary)
            "full_report"       — str (prose report for PDF)
        """
        b64_data, mime_type = self._encode_image(image_path)
        prompt = self._build_prompt(relevant_content, gps_guesses, metadata)
 
        image_part = types.Part.from_bytes(
            data=base64.b64decode(b64_data),
            mime_type=mime_type,
        )
        text_part = types.Part.from_text(text=prompt)
 
        response = self.client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=[image_part, text_part])],
        )
 
        raw = response.text.strip()
 
        # Strip markdown fences if Gemini wraps anyway
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0].strip()
 
        try:
            report = json.loads(raw)
        except json.JSONDecodeError as e:
            # Graceful fallback so the app doesn't crash
            report = {
                "location_guesses": [],
                "conflict_analysis": "JSON parse error — raw Gemini response attached.",
                "key_information": {
                    "best_guess": "Unknown",
                    "key_people": [],
                    "key_places": [],
                    "key_events": [],
                    "confidence_summary": "Could not parse Gemini output.",
                },
                "full_report": raw,
                "_parse_error": str(e),
            }
        return report
