"""Find geographically grounded UK relevance in an official activity source.

Only visible content in an article/main section is considered. A UK domain,
navigation footer, company contact address or source locale never qualifies.
Signals are suggestions for source review, NOT AI semantic verification.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

UK_PLACE = re.compile(
    r"\b(?:U\.K\.|UK|United Kingdom|Great Britain|Britain|British|"
    r"England|English|Scotland|Scottish|Wales|Welsh|Northern Ireland|"
    r"London|Clerkenwell|King[’']?s Cross|Tottenham Court Road|"
    r"Paddington|Canary Wharf|Battersea|Business Design Centre|"
    r"Manchester|Birmingham|Leeds|Liverpool|Sheffield|Bristol|"
    r"Newcastle(?: upon Tyne)?|Nottingham|Leicester|Coventry|"
    r"Brighton|Oxford|Cambridge|Bath|York|"
    r"Glasgow|Edinburgh|Cardiff|Belfast|"
    r"Surrey|Kent|Essex|Hampshire|Berkshire|Devon|Cornwall|"
    r"Hertfordshire|Buckinghamshire|Oxfordshire|Greater Manchester|"
    r"West Midlands|West Yorkshire|North Yorkshire|Warwick|Southampton|Portsmouth|Islington|Heathrow|Gatwick|Stratford|Plymouth|Norwich|Wolverhampton|Reading|Cheltenham)\b", re.I
)
# Do not treat a generic UK address or a sidebar sign-up prompt as an activity.
ADMIN = re.compile(
    r"\b(?:contact us|contact details|head office|registered office|"
    r"telephone|telephone number|call us|fax|VAT number|cookie|privacy|"
    r"newsletter sign.?up|careers|terms & conditions|email address|"
    r"how to find us|our locations|legal notice|imprint)\b", re.I
)
ACTIVITY_CONTEXT = re.compile(
    r"\b(?:event|exhibition|exhibit|showcase|design week|launch(?:ed|ing)?|"
    r"opening|opened|project|installation|illuminat(?:ed|ion|ing)|"
    r"museum|gallery|university|library|hospital|school|pavilion|"
    r"workshop|CPD|conference|showroom|studio|venue|"
    r"partner(?:ship|ed)?|sponsor(?:ed|ship)?|campaign|"
    r"host(?:ed|ing)?|took place|will take place|"
    r"client|customer|our UK team|the UK team|"
    r"lighting scheme|lighting design for|architectural project)\b", re.I
)
FOREIGN_LOCATION = re.compile(
    r"\b(?:Milan|Milano|Rome|Roma|Barcelona|Dubai|Riyadh|Abu Dhabi|"
    r"Cologne|Köln|Düsseldorf|Dusseldorf|Paris|Vienna|Berlin|"
    r"Amsterdam|Copenhagen|Brussels|Munich|Turin|Italy|Germany|"
    r"Spain|France|Austria|Denmark|Belgium|UAE)\b", re.I
)
SKIP_TAGS = {"script","style","noscript","nav","footer","header","aside","form",
             "iframe","svg","template","dialog"}
BLOCKS = {"h1","h2","h3","h4","p","li"}
MIN_CHARS = 55


class ArticleBlocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.active = []
        self.blocks = []
        self.article_seen = False
        self.main_seen = False
        self.after_h1 = False

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        role = (props.get("role") or "").lower()
        classes = (props.get("class") or "").lower()
        is_main = tag == "main" or role == "main"
        is_article = tag == "article" or bool(re.search(r"\barticle[-_\s]?(?:body|content|text)\b", classes))
        self.stack.append((tag,is_main,is_article,tag in SKIP_TAGS))
        self.main_seen |= is_main
        self.article_seen |= is_article
        if tag in BLOCKS:
            self.active.append([tag, len(self.stack), [], self.article_seen, self.main_seen])

    def handle_data(self, data):
        if self.active and not any(t[3] for t in self.stack):
            self.active[-1][2].append(data)

    def handle_endtag(self, tag):
        if self.active and tag == self.active[-1][0]:
            _, _, pieces, in_article, in_main = self.active.pop()
            value = " ".join(" ".join(pieces).split())
            if value:
                self.blocks.append((value,in_article,in_main,self.after_h1))
            if tag == "h1":
                self.after_h1 = True
        if self.stack:
            idx = next((i for i in range(len(self.stack)-1,-1,-1) if self.stack[i][0]==tag),None)
            if idx is not None:
                del self.stack[idx:]
        self.article_seen=any(x[2] for x in self.stack)
        self.main_seen=any(x[1] for x in self.stack)


def extract_blocks(html):
    parser=ArticleBlocks()
    parser.feed(html)
    candidates=parser.blocks
    article=[text for text,flag,_,_ in candidates if flag]
    main=[text for text,_,flag,_ in candidates if flag]
    if len(" ".join(article))>=MIN_CHARS:
        return article[:24]
    if len(" ".join(main))>=MIN_CHARS:
        return main[:24]
    # Some official marketing websites render their story in generic divs,
    # without semantic main/article elements. Take nearby prose after <h1>,
    # excluding navigation, forms, footer and related-page furniture.
    after_heading=[text for text,_,_,after in candidates if after]
    return after_heading[:16]


class VisiblePage(HTMLParser):
    """Visible text fallback for official sites that omit semantic article tags."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in {"meta", "link", "img", "br", "hr", "input", "source", "wbr"}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            idx = len(self.stack) - 1 - self.stack[::-1].index(tag)
            del self.stack[idx:]

    def handle_data(self, value):
        if any(t in SKIP_TAGS or t in {"head"} for t in self.stack):
            return
        text = " ".join(value.split())
        if len(text) > 3:
            self.parts.append(text)


def fallback_article_text(html, title):
    parser = VisiblePage()
    parser.feed(html)
    text = " ".join(parser.parts)
    # Do not search arbitrary site content. Anchor the scan to the actual
    # document headline and limit it to the nearby readable article body.
    anchor = " ".join(unescape(title).split()).casefold()
    i = text.casefold().find(anchor)
    if i < 0:
        return []
    body = text[i:i+4200]
    return [body[start:start+400] for start in range(0,len(body),300)][:14]


def uk_activity_evidence(html, title, source_url, checked_at):
    """Return a short *verbatim* source excerpt when a specific UK link is found."""
    if not source_url.startswith("https://"):
        return None
    foreign_title=bool(FOREIGN_LOCATION.search(title))
    blocks=extract_blocks(html)
    # When a real article body exists, don't let nearby recommendation cards
    # or unrelated main-page messages contaminate the activity's geography.
    has_article_tag = bool(re.search(r"<article\b", html, re.I))
    if not has_article_tag or len(" ".join(blocks)) < MIN_CHARS:
        blocks=blocks+fallback_article_text(html,title)
    for block in blocks:
        if ADMIN.search(block):
            continue
        if len(block)<30 or len(block)>2400:
            continue
        matches=list(UK_PLACE.finditer(block))
        if not matches:
            continue
        for m in matches:
            local_context=block[max(0,m.start()-135):min(len(block),m.end()+175)]
            # The UK location needs to be connected to something that the
            # company is doing there, not to a historic example, an office
            # address, a market statistic or a generic UK mention.
            if not ACTIVITY_CONTEXT.search(local_context):
                continue
            if re.search(r"\b(?:Victorian|in the nineteenth century|statistics? (?:show|suggest)|"
                         r"percentage of workers|of workers in|survey respondents)\b", local_context, re.I):
                continue
            # If headline unambiguously identifies an overseas event, a
            # UK office mention elsewhere must not reassign its geography.
            if foreign_title and not re.search(
                r"\b(?:UK (?:leg|event|edition|tour|launch)|London (?:edition|event|launch)|(?:separate|second|further) (?:event|launch|exhibition) in (?:the UK|London)|also took place in (?:the UK|London))\b", block, re.I
            ):
                continue
            start=max(0,m.start()-100)
            end=min(len(block),m.end()+170)
            excerpt=block[start:end].strip(" ,.;")
            if start>0:
                excerpt="…"+excerpt
            if end<len(block):
                excerpt+="…"
            if not UK_PLACE.search(excerpt):
                continue
            return {
                "quote": excerpt[:300],
                "place": m.group(0),
                "origin": "official_article_body",
                "evidence_type": "uk_specific_activity",
                "source_url": source_url,
                "checked_at": checked_at,
                "review_status": "automatically_extracted",
            }
    return None


def fetch_article_evidence(record, domains, checked_at, timeout=12):
    """Restrict article reads to known, HTTPS, first-party brand domains."""
    source=record.get("source_url") or ""
    host=(urlsplit(source).hostname or "").lower()
    allowed=domains.get(record.get("brand"),set())
    if not source.startswith("https://") or not any(
        host == domain or host.endswith("." + domain) for domain in allowed
    ):
        return None, "untrusted_source"
    path=urlsplit(source).path.strip("/")
    if len(path.split("/"))<3:
        return None, "listing_page"
    try:
        req=Request(source,headers={
            "User-Agent":"Mozilla/5.0 (compatible; iGuzziniUK-MarketingResearch/1.0)",
            "Accept":"text/html,application/xhtml+xml",
        })
        with urlopen(req,timeout=timeout) as response:
            final_host=(urlsplit(response.url).hostname or "").lower()
            if not any(final_host==d or final_host.endswith("."+d) for d in allowed):
                return None,"cross_domain_redirect"
            if "html" not in response.headers.get("Content-Type","").lower():
                return None,"not_html"
            raw=response.read(700000)
        result=uk_activity_evidence(raw.decode("utf-8","replace"),record.get("title") or "",source,checked_at)
        return result, "uk_evidence_found" if result else "no_uk_context"
    except Exception as exc:
        return None,"unavailable_"+type(exc).__name__
