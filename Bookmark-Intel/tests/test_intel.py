from intel import FetchResult, analyze_html, render_markdown


def fake(html: str, url: str = "https://example.com/post") -> FetchResult:
    return FetchResult(
        requested_url=url,
        final_url=url,
        redirects=[],
        status_code=200,
        content_type="text/html",
        text=html,
        byte_count=len(html.encode("utf-8")),
    )


def test_article_activates_editorial_and_entities():
    data = analyze_html(fake('''
    <html lang="en"><head>
      <title>How Tiny Models Work</title>
      <meta name="description" content="A detailed explanation of how compact AI models trade memory, speed, and capability.">
      <script type="application/ld+json">{
        "@context":"https://schema.org","@type":"Article","headline":"How Tiny Models Work",
        "author":{"@type":"Person","name":"Ada Example"},"datePublished":"2026-09-01",
        "publisher":{"@type":"Organization","name":"Example Lab"}
      }</script>
    </head><body><article><h1>How Tiny Models Work</h1>
      <p>This article explains artificial intelligence model compression and why smaller models can be useful on local hardware.</p>
    </article></body></html>'''))
    assert data["classification"]["kind"] == "article"
    assert data["classification"]["confidence"] >= 0.7
    assert "editorial" in data["sections"]
    assert any(entity["name"] == "Ada Example" for entity in data["entities"])
    assert "ai" in data["tags"]
    assert "How Tiny Models Work" in render_markdown(data)


def test_github_url_is_repo_and_gets_technical_section():
    url = "https://github.com/example/cool-tool"
    data = analyze_html(fake('''
    <html><head><title>example/cool-tool: Useful local software</title>
    <meta name="description" content="Open source Python developer tool with an API and documentation."></head>
    <body><main><h1>cool-tool</h1><p>This repository contains source code, installation notes, docs, and an API example.</p>
    <a href="https://example.com/docs">Documentation</a></main></body></html>''', url))
    assert data["classification"]["kind"] == "github_repository"
    assert data["sections"]["technical"]["repository_owner"] == "example"
    assert data["sections"]["technical"]["repository_name"] == "cool-tool"
    assert data["bookmark"]["suggested_folder"] == "Technology / Source Code"
    assert data["links"]["important"]


def test_dynamic_sections_do_not_emit_empty_commerce_section():
    data = analyze_html(fake('''
    <html><head><title>Simple page</title><meta name="description" content="A simple personal page with enough descriptive text to summarize its purpose correctly."></head>
    <body><main><p>This is a plain webpage without product offers, video metadata, or editorial structured data.</p></main></body></html>'''))
    assert "commercial" not in data["sections"]
    assert "media" not in data["sections"]


def test_academic_paper_arxiv_extraction():
    url = "https://arxiv.org/abs/2301.00000"
    html = '''
    <html><head>
      <title>Foundations of Large Reasoning Models</title>
      <meta name="citation_title" content="Foundations of Large Reasoning Models">
      <meta name="citation_author" content="Smith, John">
      <meta name="citation_author" content="Doe, Jane">
      <meta name="citation_date" content="2026/01/15">
      <meta name="citation_pdf_url" content="https://arxiv.org/pdf/2301.00000">
    </head><body><main>
      <h1>Foundations of Large Reasoning Models</h1>
      <p>We explore transformer architectures and neural network reasoning bounds.</p>
    </main></body></html>'''
    data = analyze_html(fake(html, url))
    assert data["classification"]["kind"] == "academic_paper"
    assert data["classification"]["category"] == "Research / Paper"
    assert "academic" in data["sections"]
    assert data["sections"]["academic"]["pdf_url"] == "https://arxiv.org/pdf/2301.00000"
    assert len(data["sections"]["academic"]["authors"]) == 2
    assert any(e["name"] == "Smith, John" for e in data["entities"])
    assert "research" in data["tags"]


def test_hacker_news_forum_not_classified_as_shopping():
    url = "https://news.ycombinator.com/item?id=999999"
    html = '''
    <html><head><title>Discussion on System Architecture | Hacker News</title></head>
    <body><div id="content">
      <p>The price of distributed coordination is often overlooked by developers.</p>
      <a href="https://github.com/example/consensus">consensus repo</a>
    </div></body></html>'''
    data = analyze_html(fake(html, url))
    assert data["classification"]["kind"] == "forum_discussion"
    assert data["classification"]["category"] == "Community / Discussion"
    assert "shopping" not in data["tags"]
    assert "product" != data["classification"]["kind"]
    assert data["bookmark"]["suggested_folder"] == "Community / Discussions / Hacker News"


def test_anime_manga_database_extraction():
    url = "https://myanimelist.net/anime/500/Space_Adventure"
    html = '''
    <html><head><title>Space Adventure - MyAnimeList.net</title></head>
    <body><main>
      <h1 class="title-name">Space Adventure</h1>
      <div class="score-label">8.65</div>
      <p>An iconic space anime series detailing bounty hunter adventures across the solar system.</p>
      <a href="https://space-adventure.example.com">Official Site</a>
    </main></body></html>'''
    data = analyze_html(fake(html, url))
    assert data["classification"]["kind"] == "anime_manga"
    assert data["classification"]["category"] == "Media / Anime & Manga"
    assert data["sections"]["anime_manga"]["score"] == "8.65"
    assert data["sections"]["anime_manga"]["media_type"] == "Anime"
    assert data["bookmark"]["suggested_folder"] == "Media / Anime & Manga"


def test_gaming_store_page_extraction():
    url = "https://store.steampowered.com/app/12345/Cosmic_Odyssey/"
    html = '''
    <html><head><title>Cosmic Odyssey on Steam</title><meta name="description" content="An epic role-playing video game."></head>
    <body><main>
      <h1>Cosmic Odyssey</h1>
      <div class="dev_row">Larian Studios</div>
      <p>Embark on an interactive RPG adventure in deep space.</p>
    </main></body></html>'''
    data = analyze_html(fake(html, url))
    assert data["classification"]["kind"] == "gaming"
    assert data["classification"]["category"] == "Gaming / Game"
    assert any(e["type"] == "Game" and "Cosmic Odyssey" in e["name"] for e in data["entities"])
    assert data["bookmark"]["suggested_folder"] == "Gaming / Games"


def test_long_form_essay_without_p_tags():
    url = "https://example.com/essay/modern-systems"
    html = '''
    <html><head><title>Modern Systems and State - Developer Blog</title></head>
    <body><div id="content">
      <span class="byline"><a href="/user/alice">alice</a></span>
      <pre>
This is the opening section of a long-form technical essay on modern software architecture.

We examine why distributed state machines require careful synchronization and how developers can avoid cascading failures.

Through rigorous isolation boundaries and deterministic protocols, systems remain maintainable across multi-year lifecycles.
      </pre>
    </div></body></html>'''
    data = analyze_html(fake(html, url))
    assert data["classification"]["kind"] == "article"
    assert "editorial" in data["sections"]
    assert any(e["name"] == "alice" for e in data["entities"])
    assert data["quality"]["content_text_chars_considered"] > 200


def test_link_ranking_excludes_boilerplate():
    url = "https://github.com/org/repo"
    html = '''
    <html><head><title>org/repo</title></head>
    <body><article class="markdown-body">
      <h1>Cool Tool</h1>
      <p>Check out our official docs and package.</p>
      <a href="https://cooltool.readthedocs.io">Official Docs</a>
      <a href="https://pypi.org/project/cooltool">PyPI Package</a>
    </article>
    <footer>
      <a href="https://github.com/pricing">Pricing</a>
      <a href="https://docs.github.com">GitHub Docs</a>
      <a href="https://github.com/site-policy/privacy-policies">Privacy</a>
      <a href="https://github.com/signup">Sign up</a>
    </footer></body></html>'''
    data = analyze_html(fake(html, url))
    urls = [link["url"] for link in data["links"]["important"]]
    assert "https://cooltool.readthedocs.io" in urls
    assert "https://pypi.org/project/cooltool" in urls
    assert "https://github.com/pricing" not in urls
    assert "https://docs.github.com" not in urls
    assert "https://github.com/signup" not in urls
