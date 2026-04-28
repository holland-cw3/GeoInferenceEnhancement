from geoclip import GeoCLIP
from google import genai
import PIL.Image
import torch

class AggregationLayer:
    """
        Extracts relevant content from the scraped pages, and produces GPS coordinate guesses (along with confidence scores)
        and also generalized locations (GPS -> Google Maps)
    """
    def __init__(self):
        self.client = genai.Client()
        self.geoClipModel = GeoCLIP()


    def extract_relevant_page_content(self, page_content, image):
        """
            Pass the image(s) and page content to Gemini to extract what it deems "relevant" 
            content with respect to it's analysis of the image. If page content includes
            locations, people, days, events, etc. It should be kept for the final report
        """

        model = "gemini-3-flash-preview"
        prompt = ""

        # pic_to_analyze = PIL.Image.open(media / image)
        
        response = self.client.models.generate_content(
            model=model,
            contents=[prompt, image],
            temperature=0
        )

        print(response.text)
        return None
    

    def geoclip_inference(self, image_path):
        """
            Produce likely guesses as determined by the geoclip 
        """
        # image_path = "image.png"

        top_pred_gps, top_pred_prob = self.geoClipModel.predict(image_path, top_k=5)

        print("Top 5 GPS Predictions")
        print("=====================")
        for i in range(5):
            lat, lon = top_pred_gps[i]
            print(f"Prediction {i+1}: ({lat:.6f}, {lon:.6f})")
            print(f"Probability: {top_pred_prob[i]:.6f}")
            print("")





