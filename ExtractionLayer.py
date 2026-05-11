from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from exif import Image


class ExtractionLayer:
    """
    Fetch a webpage, extract clean page text, download candidate images, and
    collect EXIF metadata for the rest of the geolocation pipeline.

    The returned dict keeps the first downloaded image at top level for the
    existing aggregation/conclusion code, while preserving all images in
    results["images"] for later multi-image support.
    """

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
    IMAGE_MIME_EXTENSIONS = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/tiff": ".tiff",
    }
    DOMAIN_HINTS = {
        "ca": "Canada",
        "cn": "China",
        "de": "Germany",
        "edu": "United States education domain",
        "es": "Spain",
        "fr": "France",
        "gov": "United States government domain",
        "it": "Italy",
        "jp": "Japan",
        "mil": "United States military domain",
        "ru": "Russia",
        "uk": "United Kingdom",
        "ua": "Ukraine",
        "us": "United States",
    }

    def __init__(
        self,
        url: str,
        image_dir: str | os.PathLike[str] = "images",
        timeout: int = 15,
        max_images: int = 5,
        session: requests.Session | None = None,
    ):
        self.url = url.strip()
        self.image_dir = Path(image_dir)
        self.timeout = timeout
        self.max_images = max_images
        self.session = session or requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "GeoInferenceEnhancement/1.0"
            )
        }

    def run(self, max_images: int | None = None) -> dict[str, Any]:
        """
        Return extraction results for the downstream pipeline.

        Shape:
        {
            "url": str,
            "domain_context": {"domain": str, "tld": str, "country_hint": str | None},
            "page_content": str,
            "images": [
                {
                    "source_url": str,
                    "image_path": str,
                    "metadata": dict,
                    "surrounding_text": str,
                    "alt_text": str,
                }
            ],
            "image_path": str | None,
            "metadata": dict,
            "surrounding_text": str,
            "errors": list[str],
        }
        """
        limit = max_images if max_images is not None else self.max_images
        response = self._get(self.url)
        content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
        domain_context = self._domain_context(self.url)
        errors: list[str] = []

        if content_type.startswith("image/"):
            image_record = self._save_image_response(
                response=response,
                source_url=self.url,
                surrounding_text="",
                alt_text="",
            )
            images = [image_record]
            return self._build_results(
                page_content="",
                images=images,
                domain_context=domain_context,
                errors=errors,
            )

        soup = BeautifulSoup(response.text, "html.parser")
        page_content = self._clean_page_content(soup)
        candidates = self._find_image_candidates(soup)

        images = []
        seen_urls = set()
        for candidate in candidates:
            if len(images) >= limit:
                break

            image_url = candidate["source_url"]
            if image_url in seen_urls:
                continue
            seen_urls.add(image_url)

            try:
                image_response = self._get(image_url, stream=True)
                image_content_type = image_response.headers.get("Content-Type", "").split(";")[0].lower()
                if not self._looks_like_supported_image(image_url, image_content_type):
                    continue

                images.append(
                    self._save_image_response(
                        response=image_response,
                        source_url=image_url,
                        surrounding_text=candidate["surrounding_text"],
                        alt_text=candidate["alt_text"],
                    )
                )
            except requests.RequestException as exc:
                errors.append(f"Could not download image {image_url}: {exc}")

        return self._build_results(
            page_content=page_content,
            images=images,
            domain_context=domain_context,
            errors=errors,
        )

    def _get(self, url: str, stream: bool = False) -> requests.Response:
        response = self.session.get(url, headers=self.headers, timeout=self.timeout, stream=stream)
        response.raise_for_status()
        return response

    def _build_results(
        self,
        page_content: str,
        images: list[dict[str, Any]],
        domain_context: dict[str, str | None],
        errors: list[str],
    ) -> dict[str, Any]:
        primary = images[0] if images else {}
        return {
            "url": self.url,
            "domain_context": domain_context,
            "page_content": page_content,
            "images": images,
            "image_path": primary.get("image_path"),
            "metadata": primary.get("metadata", {}),
            "surrounding_text": primary.get("surrounding_text", ""),
            "errors": errors,
        }

    def _clean_page_content(self, soup: BeautifulSoup) -> str:
        soup = BeautifulSoup(str(soup), "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "header", "footer"]):
            tag.decompose()

        lines = []
        seen = set()
        for text in soup.stripped_strings:
            cleaned = self._normalize_whitespace(text)
            if len(cleaned) < 2 or cleaned in seen:
                continue
            seen.add(cleaned)
            lines.append(cleaned)

        return "\n".join(lines)

    def _find_image_candidates(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        candidates = []

        for image in soup.find_all("img"):
            source_url = self._best_image_source(image)
            if not source_url:
                continue
            candidates.append(
                {
                    "source_url": urljoin(self.url, source_url),
                    "surrounding_text": self._surrounding_text(image),
                    "alt_text": self._normalize_whitespace(
                        image.get("alt") or image.get("title") or ""
                    ),
                }
            )

        for selector, attr in [
            (("meta", {"property": "og:image"}), "content"),
            (("meta", {"name": "twitter:image"}), "content"),
            (("link", {"rel": "image_src"}), "href"),
        ]:
            tag = soup.find(*selector)
            if tag and tag.get(attr):
                candidates.append(
                    {
                        "source_url": urljoin(self.url, tag[attr]),
                        "surrounding_text": "",
                        "alt_text": "",
                    }
                )

        return candidates

    def _best_image_source(self, image_tag: Any) -> str | None:
        for attr in ("src", "data-src", "data-original", "data-lazy-src"):
            value = image_tag.get(attr)
            if value:
                return value.strip()

        srcset = image_tag.get("srcset") or image_tag.get("data-srcset")
        if not srcset:
            return None

        last_candidate = srcset.split(",")[-1].strip()
        return last_candidate.split()[0] if last_candidate else None

    def _surrounding_text(self, image_tag: Any) -> str:
        text_parts = []
        for attr in ("alt", "title"):
            value = image_tag.get(attr)
            if value:
                text_parts.append(value)

        caption = image_tag.find_next("figcaption")
        if caption:
            text_parts.append(caption.get_text(" ", strip=True))

        container = image_tag.find_parent(["figure", "article", "section", "div", "main", "body"])
        if container:
            text_parts.append(container.get_text(" ", strip=True))

        return self._normalize_whitespace(" ".join(text_parts))[:1500]

    def _save_image_response(
        self,
        response: requests.Response,
        source_url: str,
        surrounding_text: str,
        alt_text: str,
    ) -> dict[str, Any]:
        content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
        extension = self._image_extension(source_url, content_type)
        digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
        path = self.image_dir / f"scraped_{digest}{extension}"

        self.image_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        metadata = self._extract_metadata(path)
        return {
            "source_url": source_url,
            "image_path": str(path),
            "metadata": metadata,
            "surrounding_text": surrounding_text,
            "alt_text": alt_text,
        }

    def _extract_metadata(self, image_path: str | os.PathLike[str]) -> dict[str, Any]:
        try:
            with open(image_path, "rb") as image_file:
                image = Image(image_file)
        except Exception as exc:
            return {"metadata_error": str(exc)}

        if not getattr(image, "has_exif", False):
            return {}

        metadata: dict[str, Any] = {}
        for tag in image.list_all():
            try:
                value = image.get(tag)
            except Exception:
                continue
            metadata[tag] = self._json_safe(value)

        latitude = self._gps_decimal(
            metadata.get("gps_latitude"),
            metadata.get("gps_latitude_ref"),
        )
        longitude = self._gps_decimal(
            metadata.get("gps_longitude"),
            metadata.get("gps_longitude_ref"),
        )
        if latitude is not None and longitude is not None:
            metadata["gps_coordinates"] = [latitude, longitude]

        return metadata

    def _gps_decimal(self, dms: Any, ref: str | None) -> float | None:
        if not dms or len(dms) != 3:
            return None

        degrees, minutes, seconds = (float(part) for part in dms)
        decimal = degrees + minutes / 60 + seconds / 3600
        if ref in {"S", "W"}:
            decimal *= -1
        return round(decimal, 6)

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, tuple):
            return [self._json_safe(item) for item in value]
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        return value

    def _looks_like_supported_image(self, url: str, content_type: str) -> bool:
        if content_type in self.IMAGE_MIME_EXTENSIONS:
            return True

        path = urlparse(url).path.lower()
        extension = os.path.splitext(path)[1]
        return extension in self.IMAGE_EXTENSIONS

    def _image_extension(self, url: str, content_type: str) -> str:
        if content_type in self.IMAGE_MIME_EXTENSIONS:
            return self.IMAGE_MIME_EXTENSIONS[content_type]

        path = urlparse(url).path.lower()
        extension = os.path.splitext(path)[1]
        if extension in self.IMAGE_EXTENSIONS:
            return extension

        guessed = mimetypes.guess_extension(content_type or "")
        return guessed if guessed in self.IMAGE_EXTENSIONS else ".jpg"

    def _domain_context(self, url: str) -> dict[str, str | None]:
        hostname = urlparse(url).hostname or ""
        parts = hostname.lower().split(".")
        tld = parts[-1] if parts else ""
        second_level = parts[-2] if len(parts) > 1 else ""
        hint_key = second_level if second_level in {"gov", "edu", "mil"} else tld

        return {
            "domain": hostname,
            "tld": tld,
            "country_hint": self.DOMAIN_HINTS.get(hint_key),
        }

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()
