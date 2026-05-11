# ExtractionLayer Usage

`ExtractionLayer` fetches a URL, cleans webpage text, downloads image candidates, extracts EXIF metadata, and returns data for the aggregation/conclusion pipeline.

## Basic Usage

```python
from ExtractionLayer import ExtractionLayer

results = ExtractionLayer("https://example.com/article").run()
```

## Return Shape

```python
{
    "url": "https://example.com/article",
    "domain_context": {
        "domain": "example.com",
        "tld": "com",
        "country_hint": None
    },
    "page_content": "Cleaned visible webpage text...",
    "images": [
        {
            "source_url": "https://example.com/image.jpg",
            "image_path": "images/scraped_abc123.jpg",
            "metadata": {},
            "surrounding_text": "Nearby caption/article text...",
            "alt_text": "Image alt text"
        }
    ],
    "image_path": "images/scraped_abc123.jpg",
    "metadata": {},
    "surrounding_text": "Nearby caption/article text...",
    "errors": []
}
```

## Fields

- `page_content`: cleaned page text with HTML/script/style/navigation removed.
- `domain_context`: domain, TLD, and a simple country/domain hint when available.
- `images`: all downloaded image records.
- `image_path`: primary image path, kept for the current single-image pipeline.
- `metadata`: EXIF metadata from the primary image. If GPS exists, includes `gps_coordinates`.
- `surrounding_text`: caption, alt text, and nearby page text for the primary image.
- `errors`: non-fatal image download errors.


For multiple images, iterate over `results["images"]`.
