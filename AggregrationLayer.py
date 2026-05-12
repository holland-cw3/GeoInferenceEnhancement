"""
    Author: Caleb Holland
    The aggregation layer extracts relevant content from the scraped site
    and uses geoclip patch predicting on an image to provide better 
    geolocation guesses.
"""

from ImageEnhancement import ImageEnhancement
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from geoclip import GeoCLIP
from google import genai
import PIL.Image
import tempfile
import torch
import os


class AggregationLayer:
    """
        Extracts relevant content from the scraped pages, and produces GPS coordinate guesses (along with confidence scores)
        and also generalized locations (GPS -> Google Maps)
    """
    def __init__(self):
        load_dotenv() # load env variables

        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        HF_TOKEN = os.getenv("HF_TOKEN")

        os.environ["HF_TOKEN"] = HF_TOKEN # set HF token for huggingface downloads

        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.geoClipModel = GeoCLIP()
        self.geolocator = Nominatim(user_agent="GeoInferenceEnhancementPipeline")


    def extract_relevant_page_content(self, page_content):
        """
            Pass the page content to Gemini to extract what it deems "relevant" 
            content. If page content includes locations, people, days, events, etc.
            It should be kept for the final report
        """

        model = "gemini-3-flash-preview"
        prompt = f"""
            You are an information extraction system.

            Your task is to extract only relevant, high signal information that could help infer geographic location, or identify key information.

            Focus on preserving:
            - Place names (cities, towns, regions, countries)
            - Landmarks, buildings, natural features
            - Addresses, coordinates, or partial addresses
            - Street names, highways, route numbers
            - Business names that imply location
            - Languages, dialects, currency mentions
            - Local events, festivals, dates tied to place
            - Cultural or regional references
            - Names of people ONLY if they are strongly tied to a specific location context

            Remove everything else:
            - Ads, navigation text, boilerplate
            - Generic descriptions
            - Unrelated storytelling or filler
            - Repeated or redundant content

            Return Format:
            - Only return a bulleted list for each information category.
            - Each bullet should be a single fact/data point
            - Do NOT include summaries or explanations. Simply extract.
            - Do NOT infer information beyond what's present in the text.
            
            If no relevant information exists:
            Return an empty string

            Page Content:
            ---------------
            {page_content}
            ---------------
        """ 
        
        response = self.client.models.generate_content(
            model=model,
            contents=[prompt],
            temperature=0
        )

        return response.text
    

    def reverse_geocode(self, lat, lon):
        """
            Map geo coordinates to their general location for easier interpretation by gemini
            i.e. if the page content contains "Washington D.C", and the general GPS location is
            Washington D.C. this would be a much better guess.
        """

        loc_str = f"{lat}, {lon}"
        location = self.geolocator.reverse(loc_str)

        return location.address
    
    def multi_patch_predict(self, image_path):
        """
            Split image into multiple subsections and make predictions on those
        """

        image_enhancer = ImageEnhancement()
        image_enhancer.standardize_image(image_path)

        image = PIL.Image.open(image_path)
        patches = image_enhancer.get_grid_patches(image, grid=2)

        all_preds = []
        all_probs = []

        temp_files = []

        try:
            for patch in patches:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                patch.save(tmp.name)
                tmp.close()

                temp_files.append(tmp.name)

                preds, probs = self.geoClipModel.predict(tmp.name, top_k=5)

                all_preds.append(preds)
                all_probs.append(probs)

        finally:
            for f in temp_files:
                os.remove(f)

        return all_preds, all_probs



    def aggregate_predictions(self, all_preds, all_probs):
        """
            aggregate patch guesses into a 'weighted' probability
        """
        scores = {}
        for preds, probs in zip(all_preds, all_probs):
            for (lat, lon), p in zip(preds, probs):
                lat = float(lat)
                lon = float(lon)
                p = p.item() if hasattr(p, "item") else float(p)

                key = (round(lat, 2), round(lon, 2))

                scores[key] = scores.get(key, 0) + p

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked
    

    def infer_geolocation(self, image_path):
        """
            Produce likely guesses as determined by the geoclip model
        """

        all_preds, all_probs = self.multi_patch_predict(image_path)

        aggregated = self.aggregate_predictions(all_preds, all_probs)

        guesses = {}

        for i, ((lat, lon), score) in enumerate(aggregated[:10]):
            address = self.reverse_geocode(lat, lon)

            guesses[i + 1] = {"Address": address, "Prediction": (lat, lon), "Score": score}
            
        return guesses



aggregation_layer = AggregationLayer()
gps_coordinate_guesses = aggregation_layer.infer_geolocation(image_path="./images/i2.jpg")
print(gps_coordinate_guesses)