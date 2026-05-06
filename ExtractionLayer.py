from bs4 import BeautifulSoup # cleaning/webscraping
from exif import Image # for metadata extraction
import requests # fetching page html content

# Notes for Avi + Nahom:
# - We want:
#   - cleaned content. Basically We want the page content excluding the tags, in chunks (array or smth)
#       - No need to extract relevant content, as this happens in the aggregation layer
#       - One extra thing is that the domain extension (.gov, .ru) might also help us infer location, so see if you can also return a mapped
#          domain location
#   - cleaned metadata. If there are GPS coordinates, device information, timezone information, any other relevant metadata, return this.
#   - also save the image into our images folder, and then return the path to the image

class ExtractionLayer:
    def __init__(self, url):
        self.url = url