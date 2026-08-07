import hashlib
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from markdownify import markdownify


@dataclass(frozen=True)
class ExtractedWebPage:
    markdown: bytes
    metadata: dict[str, object]
    locator_map: dict[str, object]
    attachment_urls: tuple[str, ...]


class WebPageExtractor:
    def extract(self, raw_html: bytes, url: str) -> ExtractedWebPage:
        soup = BeautifulSoup(raw_html, "html.parser")
        for element in soup(["script", "style", "noscript", "template"]):
            element.decompose()

        title = self._metadata(soup, "property", "og:title") or (
            soup.title.get_text(" ", strip=True) if soup.title else None
        )
        author = self._metadata(soup, "name", "author")
        published_at = self._metadata(soup, "property", "article:published_time")
        canonical = None
        canonical_element = soup.find("link", rel="canonical")
        if canonical_element is not None:
            canonical = canonical_element.get("href")

        body = soup.body or soup
        markdown_text = markdownify(
            str(body),
            heading_style="ATX",
            bullets="-",
            strip=["nav", "footer", "aside"],
        ).strip()
        if markdown_text:
            markdown_text += "\n"

        blocks = []
        for index, element in enumerate(body.find_all(["h1", "h2", "h3", "p", "li"])):
            text = element.get_text(" ", strip=True)
            if not text:
                continue
            blocks.append(
                {
                    "ordinal": index,
                    "tag": element.name,
                    "text": text,
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                }
            )

        metadata: dict[str, object] = {
            "url": url,
            "usage_scope": "private_research",
        }
        if title:
            metadata["title"] = title
        if author:
            metadata["author"] = author
        if published_at:
            metadata["published_at"] = published_at
        if canonical:
            metadata["declared_canonical_url"] = canonical

        attachment_urls: list[str] = []
        for image in body.find_all("img", src=True):
            candidate = urljoin(url, str(image["src"]))
            if urlsplit(candidate).scheme not in {"http", "https"}:
                continue
            if candidate not in attachment_urls:
                attachment_urls.append(candidate)
            if len(attachment_urls) == 20:
                break

        return ExtractedWebPage(
            markdown=markdown_text.encode(),
            metadata=metadata,
            locator_map={"version": 1, "blocks": blocks},
            attachment_urls=tuple(attachment_urls),
        )

    @staticmethod
    def _metadata(soup: BeautifulSoup, attribute: str, value: str) -> str | None:
        element = soup.find("meta", attrs={attribute: value})
        if element is None:
            return None
        content = element.get("content")
        return str(content).strip() if content else None
