#!/usr/bin/env python3
"""강원테크노파크 게시판 한 페이지의 게시글 제목과 링크를 CSV로 저장합니다."""

import argparse
import csv
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urldefrag, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

BOARD_URL = "https://www.gwtp.or.kr/gwtp/bbsNew_list.php?code=sub01b&keyvalue=sub01"
DETAIL_LINK = re.compile(r"(?:^|/)bbs(?:new)?_(?:view|read|detail)\.php(?:[?#]|$)", re.I)


def title_column_links(soup):
    for table in soup.find_all("table"):
        column = None
        for row in table.select(":scope > tr, :scope > thead > tr, :scope > tbody > tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if column is None:
                for index, cell in enumerate(cells):
                    if "".join(cell.get_text().split()) in {"제목", "공고명", "게시글제목"}:
                        column = index
                        break
            elif column < len(cells) and not (len(cells) == 1 and cells[0].has_attr("colspan")):
                for anchor in cells[column].find_all("a", href=True):
                    if anchor.get_text(strip=True) and not anchor.has_attr("download"):
                        yield anchor
                        break


def collect_posts(
    html: bytes, page_url: str, encoding: str | None = None
) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser", from_encoding=encoding)
    base = soup.find("base", href=True)
    base_url = urljoin(page_url, base["href"]) if base else page_url
    column_links = list(title_column_links(soup))
    page_host = urlsplit(page_url).hostname
    posts = {}
    for anchor in column_links or soup.find_all("a", href=DETAIL_LINK):
        # 공지 행은 링크 안에 모집 상태 버튼과 제목을 함께 표시합니다.
        title_node = anchor.select_one("span.ellipsis") or anchor
        title = title_node.get_text(" ", strip=True)
        href = anchor["href"].strip()
        if not title or not href or href.startswith("#"):
            continue
        link = urldefrag(urljoin(base_url, href)).url
        parts = urlsplit(link)
        if parts.scheme not in {"http", "https"} or not parts.hostname or link == page_url:
            continue
        if not column_links and parts.hostname != page_host:
            continue
        board = parse_qs(parts.query).get("code")
        if board is None or "sub01b" in board:
            posts.setdefault(link, title)

    return [(title, link) for link, title in posts.items()]


def fetch_page(session: requests.Session, url: str) -> tuple[bytes, str, str | None]:
    with session.get(url, timeout=(10, 30)) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        encoding = response.encoding if "charset=" in content_type else None
        return response.content, response.url, encoding


def full_title(session: requests.Session, link: str, listed_title: str) -> str:
    try:
        html, _, encoding = fetch_page(session, link)
    except requests.RequestException as error:
        print(f"상세 제목을 읽지 못해 목록 제목을 사용합니다: {error}", file=sys.stderr)
        return listed_title

    soup = BeautifulSoup(html, "html.parser", from_encoding=encoding)
    for heading in soup.select("table.table-striped th[colspan]"):
        text = heading.get_text(" ", strip=True)
        match = re.search(r"(?:^|\s)제\s*목\s*[:：]\s*(.+)", text, re.DOTALL)
        if match:
            return match.group(1).strip()

    print(f"상세 페이지에서 제목을 찾지 못해 목록 제목을 사용합니다: {link}", file=sys.stderr)
    return listed_title


def crawl_board() -> list[tuple[str, str]]:
    with requests.Session() as session:
        html, page_url, encoding = fetch_page(session, BOARD_URL)
        posts = collect_posts(html, page_url, encoding)
        detail_url = urljoin(page_url, "bbsNew_view.php") + "?"
        for index, (title, link) in enumerate(posts):
            if title.endswith(("..", "…")) and link.startswith(detail_url):
                posts[index] = (full_title(session, link, title), link)
    return posts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=Path("result.csv"))
    parser.add_argument("--html", type=Path, help="저장한 게시판 HTML에서 목록에 표시된 제목을 추출")
    args = parser.parse_args()

    try:
        if args.html:
            posts = collect_posts(args.html.read_bytes(), BOARD_URL)
        else:
            posts = crawl_board()
        if not posts:
            parser.exit(1, "게시글 링크를 찾지 못했습니다. 게시판 HTML을 확인하세요.\n")

        with TemporaryDirectory(dir=args.output.parent) as directory:
            temp_path = Path(directory) / "result.csv"
            with temp_path.open("w", encoding="utf-8-sig", newline="") as output:
                writer = csv.writer(output)
                writer.writerow(("title", "link"))
                writer.writerows(posts)
            temp_path.replace(args.output)
    except (requests.RequestException, OSError) as error:
        parser.exit(1, f"수집 실패: {error}\n")

    print(f"{args.output}: 게시글 {len(posts)}건 저장")


if __name__ == "__main__":
    main()
