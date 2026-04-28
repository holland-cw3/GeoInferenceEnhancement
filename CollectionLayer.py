from bs4 import BeautifulSoup
from exif import Image
import requests

class CollectionLayer:
    def __init__(self, url):
        self.url = url