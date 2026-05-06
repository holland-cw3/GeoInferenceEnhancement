# GeoInferenceEnhancement

## Team

| Team Member        | Responsibilities                                                                 |
|-------------------|----------------------------------------------------------------------------------|
| Avi       |  Metadata & Text Content extraction                    |
| Caleb    | Aggregation Layer: Relevant Content Extraction + Geoclip Image Grid Patching |
| Nahom  |  Metadata & Text Content extraction + Aggregation Layer Assistance|
| Rishi   | Frontend + PDF Report generation |
| Zyad    | Conclusion Layer / Final Report information |


## Motivation:

Image metadata and geolocation extraction are a major part of OSINT investigations. As we learned in class, exiftool can be used to extract metadata, including the author, GPS coordinates, device info, and more. Metadata, however, can be edited and removed, making the integrity of images malleable. In the ideal world, every image would contain accurate geolocation data, or any data at all, for that matter. But this isn’t the case.

AI/ML models have been developed to play the role of “GeoGuesser”, attempting to guess GPS coordinates using image feature extraction, but these models tend to default their primary guesses to popularized locations, which can be quite inaccurate.

## Project Scope: 

We want to build a more comprehensive inference system to provide more confident GPS coordinate guesses.

We want to build a webscraper using Beautiful Soup to extract an image (or images) along with its surrounding content as extra information.

The image(s) will then pass through the “image confidence pipeline,” which consists of a few parts:
Images will be prodded for their metadata using exif
Images will be passed to an existing ML model, GeoClip, to produce the top k likely GPS coordinate candidates.
GeoClip tends to bias predictions toward frequently represented locations, which can reduce accuracy for less common scenes.” 

Afterwards, the metadata (if any exists) in combination with the surrounding content from the website, and the top k coordinates will all be passed through the Gemini API. Gemini will then use the provided data points, in addition to its own analysis of the image, to produce location guesses, each paired with 1. A confidence value, and 2. A report explaining the reasoning behind its picks and confidence values. This report may also include conflict analysis, in the case that the metadata produced by EXIF disagrees with other information (site content and GeoClip conclusions).

The report(s) and final guess for location(s) will be displayed in a Streamlit frontend, which allows a user to provide a URL to the website they wish to scrape.

## Pipeline:

<img width="681" height="590" alt="image" src="https://github.com/user-attachments/assets/40afacd1-b03a-4b03-8628-06fb96ddab7f" />


## Tech Stack:
Streamlit - Frontend
Streamlit Folium (Interactive maps)
Beautiful Soup (web scraping: image + content extraction)
exif · PyPI - metadata extraction
Gemini API - Image Analysis and Confidence Reporting
GeoClip - Coordinate Guessing
