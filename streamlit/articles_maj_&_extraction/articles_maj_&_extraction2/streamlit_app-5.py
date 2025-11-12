# ademe_app_final.py
import streamlit as st
import sqlite3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re
import json
import time
import hashlib
import threading

# ==================== CONFIGURATION ====================
FEEDS = {
    "Agriculture, alimentation, forêt, bioéconomie": "https://librairie.ademe.fr/rss/3516-thematique-agriculture-alimentation-foret-bioeconomie.xml",
    "Air": "https://librairie.ademe.fr/rss/3145-thematique-air.xml",
    "Bâtiment": "https://librairie.ademe.fr/rss/3153-thematique-batiment.xml",
    "Changement climatique": "https://librairie.ademe.fr/rss/3147-thematique-changement-climatique.xml",
    "Consommer autrement": "https://librairie.ademe.fr/rss/2906-thematique-consommer-autrement.xml",
    "Économie circulaire et Déchets": "https://librairie.ademe.fr/rss/3426-thematique-economie-circulaire-et-dechets.xml",
    "Énergies": "https://librairie.ademe.fr/rss/3149-thematique-energies.xml",
    "Industrie et production durable": "https://librairie.ademe.fr/rss/3503-thematique-industrie-et-production-durable.xml",
    "Institutionnel": "https://librairie.ademe.fr/rss/3157-thematique-institutionnel.xml",
    "Mobilité et transports": "https://librairie.ademe.fr/rss/2901-thematique-mobilite-et-transports.xml",
    "Recherche et innovation": "https://librairie.ademe.fr/rss/2930-thematique-recherche-et-innovation.xml",
    "Société et politiques publiques": "https://librairie.ademe.fr/rss/3544-thematique-societe-et-politiques-publiques.xml",
    "Urbanisme, territoires et sols": "https://librairie.ademe.fr/rss/3509-thematique-urbanisme-territoires-et-sols.xml"
}

class SimpleHTMLParser:
    """Lightweight HTML parser without BeautifulSoup"""
    
    def extract_links(self, html_content, base_url):
        """Extract all links from HTML content"""
        links = set()
        
        # Simple regex for href attributes
        href_pattern = r'href="([^"]*)"'
        for match in re.findall(href_pattern, html_content):
            full_url = urljoin(base_url, match)
            links.add(full_url)
            
        return links
    
    def extract_script_urls(self, html_content, base_url):
        """Extract URLs from script tags"""
        urls = set()
        
        # Look for PDF URLs in scripts
        pdf_patterns = [
            r'["\'](https?://[^"\']+?\.pdf[^"\']*)["\']',
            r'(https?://[^\s<>"]+?\.pdf[^\s<>"]*)'
        ]
        
        for pattern in pdf_patterns:
            for match in re.findall(pattern, html_content, re.IGNORECASE):
                full_url = urljoin(base_url, match)
                urls.add(full_url)
                
        return urls

class ADEMEHarvester:
    def __init__(self, db_path='ademe_harvester.db'):
        self.session = requests.Session()
        self.html_parser = SimpleHTMLParser()
        self.db_path = db_path
        self.db_lock = threading.Lock()
        
        # Headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        })
        
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, theme TEXT, url TEXT UNIQUE,
                description TEXT, published TEXT,
                pdf_urls TEXT, last_updated TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pdfs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_url TEXT UNIQUE, article_url TEXT,
                article_title TEXT, detected_date TIMESTAMP,
                status TEXT
            )
        ''')
        self.conn.commit()
    
    def parse_rss_feed(self, feed_url):
        """Parse RSS feed without external dependencies"""
        try:
            response = self.session.get(feed_url, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            articles = []
            
            # Parse RSS items
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                desc_elem = item.find('description')
                date_elem = item.find('pubDate')
                
                if title_elem is not None and link_elem is not None:
                    article = {
                        'title': title_elem.text or 'Sans titre',
                        'url': link_elem.text or '',
                        'description': self.clean_html(desc_elem.text) if desc_elem is not None else 'Pas de description',
                        'published': date_elem.text if date_elem is not None else 'Date inconnue'
                    }
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            st.error(f"❌ Erreur parsing RSS: {e}")
            return []
    
    def clean_html(self, text):
        """Remove HTML tags from text"""
        if not text:
            return ""
        return re.sub('<[^<]+?>', '', text)
    
    def scan_article_for_pdfs(self, article_url, article_title):
        """Scan article page for PDF links"""
        try:
            response = self.session.get(article_url, timeout=15)
            response.raise_for_status()
            
            pdf_urls = set()
            
            # Extract links from HTML
            all_links = self.html_parser.extract_links(response.text, article_url)
            script_urls = self.html_parser.extract_script_urls(response.text, article_url)
            
            # Combine and filter PDF links
            all_urls = all_links.union(script_urls)
            
            for url in all_urls:
                if self.is_pdf_url(url):
                    pdf_urls.add(url)
            
            # Save to database
            self.save_pdf_urls(list(pdf_urls), article_url, article_title)
            
            return list(pdf_urls)
            
        except Exception as e:
            st.error(f"❌ Erreur scan {article_url}: {e}")
            return []
    
    def is_pdf_url(self, url):
        """Check if URL points to a PDF"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Check for PDF in path or common PDF indicators
        pdf_indicators = ['.pdf', '/pdf', 'download', 'attachment']
        return any(indicator in path for indicator in pdf_indicators)
    
    def save_pdf_urls(self, pdf_urls, article_url, article_title):
        """Save detected PDF URLs to database"""
        try:
            with self.db_lock:
                cursor = self.conn.cursor()
                
                for pdf_url in pdf_urls:
                    cursor.execute('''
                        INSERT OR REPLACE INTO pdfs 
                        (pdf_url, article_url, article_title, detected_date, status)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (pdf_url, article_url, article_title, datetime.now(), 'detected'))
                
                self.conn.commit()
                
        except Exception as e:
            st.error(f"❌ Erreur sauvegarde BD: {e}")
    
    def get_theme_articles(self, theme):
        """Get articles for a specific theme"""
        feed_url = FEEDS.get(theme)
        if not feed_url:
            return []
        
        return self.parse_rss_feed(feed_url)
    
    def get_detected_pdfs(self):
        """Get all detected PDFs"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT pdf_url, article_title, article_url, detected_date 
            FROM pdfs 
            ORDER BY detected_date DESC
        ''')
        return cursor.fetchall()
    
    def get_stats(self):
        """Get statistics"""
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM pdfs')
        total_pdfs = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT article_url) FROM pdfs')
        articles_with_pdfs = cursor.fetchone()[0]
        
        return total_pdfs, articles_with_pdfs

# ==================== STREAMLIT APP ====================
def main():
    st.set_page_config(
        page_title="ADEME PDF Detective",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    if 'harvester' not in st.session_state:
        st.session_state.harvester = ADEMEHarvester()
    if 'current_theme' not in st.session_state:
        st.session_state.current_theme = list(FEEDS.keys())[0]
    if 'articles' not in st.session_state:
        st.session_state.articles = []
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = {}
    
    # Custom CSS
    st.markdown("""
    <style>
    .article-box {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        background: #f9f9f9;
    }
    .pdf-found {
        border-left: 5px solid #28a745;
    }
    .no-pdf {
        border-left: 5px solid #dc3545;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.title("🔍 ADEME PDF Detective")
    st.markdown("Détection automatique de PDFs dans les publications ADEME")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("🎯 Configuration")
        
        # Theme selection
        selected_theme = st.selectbox(
            "Sélectionnez un thème ADEME",
            options=list(FEEDS.keys()),
            index=0
        )
        
        # Load articles button
        if st.button("📰 Charger les Articles", use_container_width=True, type="primary"):
            with st.spinner(f"Chargement des articles {selected_theme}..."):
                articles = st.session_state.harvester.get_theme_articles(selected_theme)
                if articles:
                    st.session_state.articles = articles
                    st.session_state.current_theme = selected_theme
                    st.success(f"✅ {len(articles)} articles chargés")
                else:
                    st.error("❌ Aucun article trouvé dans ce flux")
        
        st.markdown("---")
        st.header("📊 Statistiques")
        
        total_pdfs, articles_with_pdfs = st.session_state.harvester.get_stats()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("PDFs Détectés", total_pdfs)
        with col2:
            st.metric("Articles avec PDFs", articles_with_pdfs)
        
        st.markdown("---")
        st.header("📋 PDFs Détectés")
        
        detected_pdfs = st.session_state.harvester.get_detected_pdfs()
        if detected_pdfs:
            for pdf in detected_pdfs[:3]:  # Show last 3
                pdf_url, article_title, article_url, detected_date = pdf
                with st.expander(f"📄 {article_title[:40]}...", expanded=False):
                    st.write(f"**Article:** {article_title}")
                    st.write(f"**Détecté:** {detected_date}")
                    st.markdown(f"[🔗 Ouvrir le PDF]({pdf_url})")
        else:
            st.info("Aucun PDF détecté pour le moment")
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"📖 Articles - {st.session_state.current_theme}")
        
        if not st.session_state.articles:
            st.info("👈 Cliquez sur 'Charger les Articles' pour commencer")
        else:
            # Bulk scan option
            if st.button("🔍 Scanner Tous les Articles", use_container_width=True, type="secondary"):
                with st.spinner("Scan en cours de tous les articles..."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    total_pdfs_found = 0
                    
                    for i, article in enumerate(st.session_state.articles):
                        status_text.text(f"Scan {i+1}/{len(st.session_state.articles)}: {article['title'][:50]}...")
                        
                        pdf_urls = st.session_state.harvester.scan_article_for_pdfs(
                            article['url'], 
                            article['title']
                        )
                        
                        total_pdfs_found += len(pdf_urls)
                        st.session_state.scan_results[article['url']] = pdf_urls
                        progress_bar.progress((i + 1) / len(st.session_state.articles))
                    
                    status_text.text(f"✅ Scan complet! {total_pdfs_found} PDFs détectés")
                    st.rerun()
            
            # Display articles
            for i, article in enumerate(st.session_state.articles):
                pdf_urls = st.session_state.scan_results.get(article['url'], [])
                has_pdfs = len(pdf_urls) > 0
                
                # CSS class based on PDF detection
                box_class = "pdf-found" if has_pdfs else "no-pdf"
                
                st.markdown(f'<div class="article-box {box_class}">', unsafe_allow_html=True)
                
                col_a, col_b = st.columns([3, 1])
                
                with col_a:
                    st.write(f"**{i+1}. {article['title']}**")
                    st.write(article['description'][:200] + "..." if len(article['description']) > 200 else article['description'])
                    st.write(f"*📅 {article['published']}*")
                    st.markdown(f"[🔗 Lire l'article]({article['url']})")
                    
                    # Show detected PDFs
                    if has_pdfs:
                        st.success(f"✅ {len(pdf_urls)} PDF(s) détecté(s)")
                        for pdf_url in pdf_urls[:2]:  # Show first 2 PDFs
                            st.markdown(f"📄 [{pdf_url.split('/')[-1][:30]}...]({pdf_url})")
                
                with col_b:
                    if st.button("🔍 Scanner", key=f"scan_{i}", use_container_width=True):
                        with st.spinner("Scan en cours..."):
                            pdf_urls = st.session_state.harvester.scan_article_for_pdfs(
                                article['url'], 
                                article['title']
                            )
                            st.session_state.scan_results[article['url']] = pdf_urls
                            
                            if pdf_urls:
                                st.success(f"✅ {len(pdf_urls)} PDF(s) détecté(s)")
                            else:
                                st.warning("❌ Aucun PDF détecté")
                            
                            st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.subheader("🚀 Actions Rapides")
        
        if st.session_state.articles:
            st.info(f"**{len(st.session_state.articles)}** articles chargés")
            
            # Quick stats
            total_scanned = len(st.session_state.scan_results)
            total_pdfs = sum(len(urls) for urls in st.session_state.scan_results.values())
            
            st.metric("Articles Scannés", total_scanned)
            st.metric("PDFs Totaux", total_pdfs)
            
            # Export results
            if st.session_state.scan_results:
                export_data = []
                for article_url, pdf_urls in st.session_state.scan_results.items():
                    article = next((a for a in st.session_state.articles if a['url'] == article_url), None)
                    if article:
                        export_data.append({
                            'article_title': article['title'],
                            'article_url': article_url,
                            'pdf_urls': pdf_urls,
                            'scan_date': datetime.now().isoformat()
                        })
                
                if export_data:
                    json_data = json.dumps(export_data, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="📥 Exporter Résultats JSON",
                        data=json_data,
                        file_name=f"ademe_pdfs_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                        mime="application/json",
                        use_container_width=True
                    )
        else:
            st.warning("Chargez d'abord les articles")
        
        st.markdown("---")
        st.subheader("ℹ️ À Propos")
        st.write("""
        Cette application scanne automatiquement les articles ADEME 
        pour détecter les liens vers des documents PDF.
        
        **Fonctionnalités:**
        • Chargement automatique des flux RSS
        • Détection intelligente des PDFs
        • Base de données locale
        • Export des résultats
        """)

    # Footer
    st.markdown("---")
    total_pdfs, articles_with_pdfs = st.session_state.harvester.get_stats()
    st.caption(f"🔍 ADEME PDF Detective | 📄 {total_pdfs} PDFs détectés | 🎯 {articles_with_pdfs} articles avec PDFs | ⚡ 100% Streamlit Cloud")

if __name__ == "__main__":
    main()