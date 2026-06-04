import feedparser
import json
import os
import re
from datetime import datetime
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

RSS_FEEDS = {
    "정치": [
        "https://www.yna.co.kr/rss/politics.xml",           # 연합뉴스 정치 ✅
        "https://www.yna.co.kr/rss/economy.xml",            # 연합뉴스 (보조)
    ],
    "경제": [
        "https://www.hankyung.com/feed/economy",             # 한국경제 경제 ✅
        "https://www.hankyung.com/feed/finance",             # 한국경제 금융 ✅
    ],
    "사회": [
        "https://www.yna.co.kr/rss/society.xml",             # 연합뉴스 사회 ✅
        "https://www.yna.co.kr/rss/culture.xml",             # 연합뉴스 문화
    ],
    "IT·기술": [
        "https://feeds.feedburner.com/zdkorea",              # 지디넷코리아 ✅ (새 URL)
        "https://www.etnews.com/etnews/rss.xml",             # 전자신문 ✅
    ],
    "세계": [
        "https://www.yna.co.kr/rss/international.xml",       # 연합뉴스 국제 ✅
        "https://www.yna.co.kr/rss/all.xml",                 # 연합뉴스 전체 (보조)
    ],
}

def analyze_article(title, description):
    prompt = f"""다음 뉴스 기사를 분석해줘.

제목: {title}
내용: {description}

아래 JSON 형식으로만 응답해. 다른 말 하지 말고 JSON만:
{{
  "summary": "기사 내용을 2~3문장으로 간략히 요약",
  "positive": "이 기사로 인한 긍정적 효과 1~2문장",
  "negative": "이 기사로 인한 부정적 효과 1~2문장",
  "importance": "high 또는 mid (중요도 판단)"
}}"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"  분석 오류: {e}")
    return None

def fetch_section(section_name, urls, max_articles=5):
    articles_raw = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            count = len(feed.entries)
            print(f"    [{section_name}] {url} → {count}개 항목 수집")
            articles_raw.extend(feed.entries)
        except Exception as e:
            print(f"    [{section_name}] RSS 오류 ({url}): {e}")

    # 중복 제거 (제목 기준)
    seen = set()
    unique = []
    for entry in articles_raw:
        title = entry.get("title", "").strip()
        if title and title not in seen:
            seen.add(title)
            unique.append(entry)

    print(f"    [{section_name}] 중복 제거 후 {len(unique)}개 → 상위 {min(max_articles, len(unique))}개 분석")
    return unique[:max_articles]

def fetch_and_analyze():
    all_news = {}

    for section, urls in RSS_FEEDS.items():
        print(f"\n========== [{section}] 시작 ==========")
        entries = fetch_section(section, urls)
        articles = []

        for entry in entries:
            title = entry.get("title", "").strip()
            description = entry.get("summary", entry.get("description", "")).strip()
            description = re.sub(r'<[^>]+>', '', description)
            link = entry.get("link", "#")
            published = entry.get("published", "")

            if not title:
                continue

            print(f"  분석 중: {title[:40]}...")
            analysis = analyze_article(title, description)

            if analysis:
                articles.append({
                    "title": title,
                    "link": link,
                    "published": published,
                    "summary": analysis.get("summary", ""),
                    "positive": analysis.get("positive", ""),
                    "negative": analysis.get("negative", ""),
                    "importance": analysis.get("importance", "mid"),
                })
            else:
                print(f"  ⚠ 분석 실패: {title[:40]}")

        all_news[section] = articles
        print(f"  ✅ [{section}] 최종 {len(articles)}개 기사 완료")

    return all_news

def generate_html(news_data):
    updated_time = datetime.now().strftime("%Y년 %m월 %d일 %H:%M 기준")

    section_colors = {
        "정치": "#fb923c",
        "경제": "#0ea5e9",
        "사회": "#a78bfa",
        "IT·기술": "#34d399",
        "세계": "#f472b6",
    }

    tabs_html = ""
    for i, section in enumerate(news_data.keys()):
        color = section_colors.get(section, "#fff")
        active = "active" if i == 0 else ""
        tabs_html += f'<button class="tab-btn {active}" onclick="showTab(\'{section}\', this)"><span class="dot" style="background:{color}"></span>{section}</button>'

    sections_html = ""
    for i, (section, articles) in enumerate(news_data.items()):
        active = "active" if i == 0 else ""
        cards_html = ""

        if not articles:
            cards_html = '<div style="padding:60px;text-align:center;color:#8b949e;font-size:0.95rem;">수집된 기사가 없습니다.</div>'
        else:
            for article in articles:
                imp_class = "high" if article["importance"] == "high" else "mid"
                imp_label = "★ 주요" if article["importance"] == "high" else "▲ 관심"
                pub = article["published"][:16] if article["published"] else ""

                cards_html += f'''
                <div class="card">
                  <div class="card-header">
                    <div class="card-title">{article["title"]}</div>
                    <span class="importance {imp_class}">{imp_label}</span>
                  </div>
                  <div class="card-summary">{article["summary"]}</div>
                  <div class="effects">
                    <div class="effect positive">
                      <span class="effect-icon">✅</span>
                      <span><span class="effect-label">긍정:</span>{article["positive"]}</span>
                    </div>
                    <div class="effect negative">
                      <span class="effect-icon">⚠️</span>
                      <span><span class="effect-label">부정:</span>{article["negative"]}</span>
                    </div>
                  </div>
                  <div class="card-footer">
                    <span class="card-time">{pub}</span>
                    <a class="card-link" href="{article["link"]}" target="_blank">기사 보기 →</a>
                  </div>
                </div>'''

        sections_html += f'<div id="tab-{section}" class="section-content {active}"><div class="grid">{cards_html}</div></div>'

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>뉴스 대시보드</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:"Noto Sans KR","Apple SD Gothic Neo",sans-serif;background:#0f1117;color:#e1e4e8;min-height:100vh}}
    header{{background:linear-gradient(135deg,#1a1d2e,#16213e);border-bottom:1px solid #30363d;padding:20px 32px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}}
    .logo{{display:flex;align-items:center;gap:10px}}
    .logo-icon{{width:36px;height:36px;background:linear-gradient(135deg,#0ea5e9,#6366f1);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px}}
    .logo h1{{font-size:1.3rem;font-weight:700;color:#fff}}
    .logo span{{font-size:0.75rem;color:#8b949e;display:block;margin-top:2px}}
    .updated{{font-size:0.78rem;color:#8b949e;background:#21262d;padding:6px 14px;border-radius:20px;border:1px solid #30363d}}
    .tabs{{display:flex;gap:8px;padding:20px 32px 0;border-bottom:1px solid #21262d;overflow-x:auto}}
    .tab-btn{{padding:10px 20px;border:none;background:transparent;color:#8b949e;cursor:pointer;font-size:0.9rem;font-weight:500;border-bottom:3px solid transparent;transition:all 0.2s;white-space:nowrap}}
    .tab-btn:hover{{color:#e1e4e8}}
    .tab-btn.active{{color:#fff;border-bottom-color:#0ea5e9;font-weight:700}}
    .dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}}
    .section-content{{display:none}}
    .section-content.active{{display:block}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:20px;padding:28px 32px;max-width:1400px;margin:0 auto}}
    .card{{background:#161b22;border:1px solid #30363d;border-radius:14px;padding:22px;transition:transform 0.2s,border-color 0.2s;display:flex;flex-direction:column;gap:14px}}
    .card:hover{{transform:translateY(-3px);border-color:#58a6ff}}
    .card-header{{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}}
    .importance{{font-size:0.7rem;font-weight:700;padding:3px 10px;border-radius:20px;white-space:nowrap;flex-shrink:0}}
    .importance.high{{background:rgba(239,68,68,0.15);color:#f87171;border:1px solid rgba(239,68,68,0.3)}}
    .importance.mid{{background:rgba(234,179,8,0.15);color:#fbbf24;border:1px solid rgba(234,179,8,0.3)}}
    .card-title{{font-size:1rem;font-weight:700;line-height:1.5;color:#e6edf3}}
    .card-summary{{font-size:0.875rem;line-height:1.7;color:#c9d1d9;border-left:3px solid #30363d;padding-left:12px}}
    .effects{{display:flex;flex-direction:column;gap:8px}}
    .effect{{display:flex;align-items:flex-start;gap:10px;padding:10px 14px;border-radius:8px;font-size:0.82rem;line-height:1.6}}
    .effect.positive{{background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);color:#86efac}}
    .effect.negative{{background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);color:#fca5a5}}
    .effect-icon{{font-size:1rem;flex-shrink:0;margin-top:1px}}
    .effect-label{{font-weight:700;margin-right:4px}}
    .card-footer{{display:flex;justify-content:space-between;align-items:center;padding-top:4px;border-top:1px solid #21262d}}
    .card-time{{font-size:0.75rem;color:#8b949e}}
    .card-link{{font-size:0.78rem;color:#58a6ff;text-decoration:none;font-weight:500}}
    .card-link:hover{{text-decoration:underline}}
    @media(max-width:768px){{.grid{{grid-template-columns:1fr;padding:16px}}header{{padding:14px 16px}}.tabs{{padding:16px 16px 0}}}}
  </style>
</head>
<body>
<header>
  <div class="logo">
    <div class="logo-icon">📰</div>
    <div><h1>뉴스 대시보드</h1><span>정치 · 경제 · 사회 · IT · 세계</span></div>
  </div>
  <div class="updated">{updated_time}</div>
</header>
<div class="tabs">{tabs_html}</div>
{sections_html}
<script>
function showTab(name, btn) {{
  document.querySelectorAll('.section-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
}}
</script>
</body>
</html>'''

if __name__ == "__main__":
    print("===== 뉴스 수집 및 분석 시작 =====")
    news_data = fetch_and_analyze()
    print("\n===== HTML 생성 중 =====")
    html_content = generate_html(news_data)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("===== 완료! index.html 생성됨 =====")
