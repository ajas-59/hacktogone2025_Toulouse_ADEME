# ademe_harvester_app.py
import streamlit as st
import os
import re
import json
import time
import sqlite3
import hashlib
import threading
import concurrent.futures
from datetime import datetime
from urllib.parse import urljoin, urlparse
import base64

import requests
import feedparser
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

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

# ==================== YOUR HARVESTER CLASS ====================
class ShadowMassPDFHarvester:
    def __init__(self, max_workers=5, db_path='shadow_harvester.db'):
        self.session = requests.Session()
        self.max_workers = max_workers
        self.downloaded_urls = set()
        self.failed_urls = set()
        self.db_path = db_path
        self.db_lock = threading.Lock()

        # En-têtes HTTP
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        # Base de données
        self.init_database()

    def init_database(self):
        """Initialisation de la base de données Shadow (thread-safe)."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS harvested_pdfs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                filename TEXT,
                file_size INTEGER,
                file_hash TEXT,
                source_feed TEXT,
                harvest_date TIMESTAMP,
                status TEXT,
                article_title TEXT,
                article_url TEXT
            )
        ''')
        self.conn.commit()

    def scan_url_for_pdfs(self, url, download_dir, title=""):
        """Scan approfondi d'une URL pour trouver des PDFs"""
        pdf_urls = set()
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            extraction_methods = [
                self._extract_from_links,
                self._extract_from_scripts,
                self._extract_from_meta,
                self._extract_from_iframes,
                self._extract_from_data_attributes,
                self._extract_from_json_ld,
                self._extract_from_prestashop_scripts,
            ]
            
            for method in extraction_methods:
                try:
                    pdf_urls.update(method(soup, url))
                except Exception as e:
                    st.warning(f"Méthode {method.__name__} échouée: {e}")

            os.makedirs(download_dir, exist_ok=True)
            downloaded = []
            for pdf_url in pdf_urls:
                if pdf_url not in self.downloaded_urls:
                    if self._download_pdf_advanced(pdf_url, download_dir, title):
                        self.downloaded_urls.add(pdf_url)
                        downloaded.append(pdf_url)
                        self._log_to_database(pdf_url, title, url, status='success')
                    else:
                        self.failed_urls.add(pdf_url)
                        self._log_to_database(pdf_url, title, url, status='failed')
            return downloaded

        except Exception as e:
            st.error(f"Erreur scan de {url}: {e}")
            return []

    def _extract_from_links(self, soup, base_url):
        pdf_urls = set()
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if 'controller=attachment' in href and 'id_attachment=' in href:
                pdf_urls.add(urljoin(base_url, href))
            elif self._is_pdf_link(href):
                pdf_urls.add(urljoin(base_url, href))
        return pdf_urls

    def _extract_from_scripts(self, soup, base_url):
        pdf_urls = set()
        for script in soup.find_all('script'):
            text = script.string or ''
            patterns = [
                r'["\'](https?://[^"\']+?\.pdf[^"\']*)["\']',
                r'(https?://[^\s<>"]+?\.pdf[^\s<>"]*)',
                r'pdfUrl[=:]\s*["\']([^"\']+\.pdf[^"\']*)["\']',
                r'download[^=]*=\s*["\']([^"\']+?\.pdf[^"\']*)["\']'
            ]
            for pattern in patterns:
                for match in re.findall(pattern, text, re.IGNORECASE):
                    pdf_urls.add(urljoin(base_url, match))
        return pdf_urls

    def _extract_from_meta(self, soup, base_url):
        pdf_urls = set()
        for meta in soup.find_all('meta', content=True):
            content = meta.get('content', '')
            if isinstance(content, str) and '.pdf' in content.lower():
                pdf_urls.add(urljoin(base_url, content))
        return pdf_urls

    def _extract_from_iframes(self, soup, base_url):
        pdf_urls = set()
        for iframe in soup.find_all('iframe', src=True):
            src = iframe['src']
            if '.pdf' in src.lower():
                pdf_urls.add(urljoin(base_url, src))
        return pdf_urls

    def _extract_from_data_attributes(self, soup, base_url):
        pdf_urls = set()

        def build_attachment_url(attach_id):
            return urljoin(base_url, f"/index.php?controller=attachment&id_attachment={attach_id}")

        for tag in soup.find_all(attrs=True):
            for _, value in tag.attrs.items():
                if isinstance(value, str):
                    v = value.strip()
                    if (v.startswith('http') or v.startswith('/')) and self._is_pdf_link(v):
                        pdf_urls.add(urljoin(base_url, v))
                        continue

                    if v.startswith('{') and v.endswith('}'):
                        try:
                            data = json.loads(v)
                            if isinstance(data, dict) and 'attachments' in data and isinstance(data['attachments'], list):
                                for att in data['attachments']:
                                    att_id = att.get('id_attachment') or att.get('id')
                                    if att_id:
                                        pdf_urls.add(build_attachment_url(att_id))
                        except Exception:
                            pass

                elif isinstance(value, (list, tuple)):
                    for v in value:
                        if isinstance(v, str) and (v.startswith('http') or v.startswith('/')) and self._is_pdf_link(v):
                            pdf_urls.add(urljoin(base_url, v))

        return pdf_urls

    def _extract_from_json_ld(self, soup, base_url):
        pdf_urls = set()
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '{}')
                pdf_urls.update(self._find_pdf_in_json(data, base_url))
            except Exception:
                pass
        return pdf_urls

    def _extract_from_prestashop_scripts(self, soup, base_url):
        pdf_urls = set()

        def build_attachment_url(attach_id):
            return urljoin(base_url, f"/index.php?controller=attachment&id_attachment={attach_id}")

        for script in soup.find_all('script'):
            txt = script.string
            if not txt or 'attachments' not in txt:
                continue
            try:
                ids = set(re.findall(r'id_attachment"\s*:\s*(\d+)', txt))
                ids |= set(re.findall(r'id_attachment=\s*(\d+)', txt))
                for att_id in ids:
                    pdf_urls.add(build_attachment_url(att_id))
            except Exception:
                pass

        return pdf_urls

    def _find_pdf_in_json(self, data, base_url):
        pdf_urls = set()
        if isinstance(data, dict):
            for _, value in data.items():
                if isinstance(value, str) and '.pdf' in value.lower():
                    pdf_urls.add(urljoin(base_url, value))
                else:
                    pdf_urls.update(self._find_pdf_in_json(value, base_url))
        elif isinstance(data, list):
            for item in data:
                pdf_urls.update(self._find_pdf_in_json(item, base_url))
        return pdf_urls

    def _is_pdf_link(self, href):
        if not isinstance(href, str):
            return False
        href = href.strip()

        if 'controller=attachment' in href and 'id_attachment=' in href:
            return True

        if href.startswith('http') or href.startswith('/'):
            parsed = urlparse(href)
            path_has_pdf = parsed.path.lower().endswith('.pdf')
            query_has_pdf = '.pdf' in (parsed.query or '').lower()
            return path_has_pdf or query_has_pdf

        return False

    def _download_pdf_advanced(self, pdf_url, download_dir, title=""):
        try:
            if title:
                safe_title = re.sub(r'[^\w\-. ]', '', title).strip() or "document"
                filename = f"{safe_title}_{int(time.time())}.pdf"
            else:
                filename = os.path.basename(urlparse(pdf_url).path) or f"document_{int(time.time())}.pdf"
            filepath = os.path.join(download_dir, filename)

            st.info(f"📥 Téléchargement: {pdf_url}")
            resp = self.session.get(pdf_url, timeout=30)
            resp.raise_for_status()

            content = resp.content
            if not content.startswith(b'%PDF'):
                st.warning(f"⚠️ Non-PDF détecté: {pdf_url}")
                return False

            with open(filepath, 'wb') as f:
                f.write(content)

            size = os.path.getsize(filepath)
            if size < 1000:
                os.remove(filepath)
                st.warning(f"⚠️ Fichier trop petit: {filename}")
                return False

            st.success(f"✅ Sauvegardé: {filename} ({size} bytes)")
            return True

        except Exception as e:
            st.error(f"❌ Échec téléchargement {pdf_url}: {e}")
            return False

    def _log_to_database(self, pdf_url, title, article_url, status):
        try:
            with self.db_lock:
                cursor = self.conn.cursor()
                file_hash = hashlib.md5(pdf_url.encode()).hexdigest()
                cursor.execute('''
                    INSERT OR REPLACE INTO harvested_pdfs 
                    (url, filename, file_size, file_hash, source_feed, harvest_date, status, article_title, article_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (pdf_url, title, 0, file_hash, 'streamlit_app', datetime.now(), status, title, article_url))
                self.conn.commit()
        except Exception as e:
            st.error(f"[DB ERROR] {e}")

    def get_stats(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT status, COUNT(*) FROM harvested_pdfs GROUP BY status')
        stats = dict(cursor.fetchall())
        
        cursor.execute('SELECT COUNT(DISTINCT article_url) FROM harvested_pdfs WHERE status="success"')
        articles_with_pdfs = cursor.fetchone()[0]
        
        return stats, articles_with_pdfs

    def get_downloaded_pdfs(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT url, filename, article_title, article_url, harvest_date 
            FROM harvested_pdfs 
            WHERE status="success" 
            ORDER BY harvest_date DESC
        ''')
        return cursor.fetchall()

# ==================== STREAMLIT APP ====================
def main():
    st.set_page_config(
        page_title="Shadow PDF Harvester - ADEME",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    if 'harvester' not in st.session_state:
        st.session_state.harvester = ShadowMassPDFHarvester(max_workers=3)
    if 'current_theme' not in st.session_state:
        st.session_state.current_theme = list(FEEDS.keys())[0]
    if 'articles' not in st.session_state:
        st.session_state.articles = []
    if 'scanning' not in st.session_state:
        st.session_state.scanning = False
    
    # Header
    st.title("🕵️ Shadow PDF Harvester - ADEME")
    st.markdown("Extraction automatique de PDFs depuis les publications ADEME")
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
        
        st.session_state.current_theme = selected_theme
        
        # Load articles button
        if st.button("📰 Charger les Articles", use_container_width=True, type="primary"):
            with st.spinner(f"Chargement des articles {selected_theme}..."):
                try:
                    feed_url = FEEDS[selected_theme]
                    feed = feedparser.parse(feed_url)
                    
                    if not feed.entries:
                        st.error("Aucun article trouvé dans ce flux")
                    else:
                        st.session_state.articles = feed.entries
                        st.success(f"✅ {len(feed.entries)} articles chargés")
                except Exception as e:
                    st.error(f"Erreur chargement flux: {e}")
        
        st.markdown("---")
        st.header("📊 Statistiques")
        
        stats, articles_with_pdfs = st.session_state.harvester.get_stats()
        success_count = stats.get('success', 0)
        failed_count = stats.get('failed', 0)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("PDFs Réussis", success_count)
        with col2:
            st.metric("PDFs Échoués", failed_count)
        
        st.metric("Articles avec PDFs", articles_with_pdfs)
        
        st.markdown("---")
        st.header("📁 PDFs Téléchargés")
        
        downloaded_pdfs = st.session_state.harvester.get_downloaded_pdfs()
        if downloaded_pdfs:
            for pdf in downloaded_pdfs[:5]:  # Show last 5
                pdf_url, filename, article_title, article_url, harvest_date = pdf
                with st.expander(f"📄 {filename[:30]}..."):
                    st.write(f"**Article:** {article_title}")
                    st.write(f"**Date:** {harvest_date}")
                    st.markdown(f"[🔗 Voir PDF]({pdf_url})")
        else:
            st.info("Aucun PDF téléchargé")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"📖 Articles - {st.session_state.current_theme}")
        
        if not st.session_state.articles:
            st.info("👈 Cliquez sur 'Charger les Articles' pour commencer")
        else:
            for i, article in enumerate(st.session_state.articles):
                with st.expander(f"{i+1}. {article.get('title', 'Sans titre')}", expanded=i==0):
                    col_a, col_b = st.columns([3, 1])
                    
                    with col_a:
                        st.write(f"**Description:** {article.get('summary', 'Pas de description')[:200]}...")
                        st.write(f"**Date:** {article.get('published', 'Non spécifiée')}")
                        st.markdown(f"[🔗 Lire l'article]({article.get('link', '')})")
                    
                    with col_b:
                        if st.button("🔍 Scanner PDFs", key=f"scan_{i}", use_container_width=True):
                            st.session_state.scanning = True
                            with st.spinner("Scan en cours..."):
                                download_dir = f"ademe_pdfs_{_sanitize_dirname(st.session_state.current_theme)}"
                                title = article.get('title', f"article_{i+1}")
                                pdfs_found = st.session_state.harvester.scan_url_for_pdfs(
                                    article.get('link', ''), 
                                    download_dir, 
                                    title=title
                                )
                                
                                if pdfs_found:
                                    st.success(f"✅ {len(pdfs_found)} PDF(s) trouvé(s) et téléchargé(s)")
                                else:
                                    st.warning("❌ Aucun PDF trouvé sur cette page")
                            
                            st.session_state.scanning = False
                            st.rerun()
    
    with col2:
        st.subheader("🚀 Actions Rapides")
        
        if st.session_state.articles:
            st.info(f"{len(st.session_state.articles)} articles chargés")
            
            if st.button("🔍 Scanner Tous les PDFs", use_container_width=True, type="secondary"):
                st.session_state.scanning = True
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_articles = len(st.session_state.articles)
                total_pdfs = 0
                
                for i, article in enumerate(st.session_state.articles):
                    status_text.text(f"Scan article {i+1}/{total_articles}: {article.get('title', '')[:50]}...")
                    
                    download_dir = f"ademe_pdfs_{_sanitize_dirname(st.session_state.current_theme)}"
                    title = article.get('title', f"article_{i+1}")
                    pdfs_found = st.session_state.harvester.scan_url_for_pdfs(
                        article.get('link', ''), 
                        download_dir, 
                        title=title
                    )
                    
                    total_pdfs += len(pdfs_found)
                    progress_bar.progress((i + 1) / total_articles)
                
                status_text.text(f"✅ Scan complet: {total_pdfs} PDFs trouvés sur {total_articles} articles")
                st.session_state.scanning = False
                st.rerun()
        else:
            st.warning("Chargez d'abord les articles")
        
        st.markdown("---")
        st.subheader("📋 Export")
        
        downloaded_pdfs = st.session_state.harvester.get_downloaded_pdfs()
        if downloaded_pdfs:
            # Create downloadable report
            report_data = []
            for pdf in downloaded_pdfs:
                pdf_url, filename, article_title, article_url, harvest_date = pdf
                report_data.append({
                    'pdf_url': pdf_url,
                    'filename': filename,
                    'article_title': article_title,
                    'article_url': article_url,
                    'harvest_date': harvest_date
                })
            
            report_json = json.dumps(report_data, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Télécharger Rapport JSON",
                data=report_json,
                file_name=f"ademe_pdfs_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True
            )
        else:
            st.info("Aucun PDF à exporter")

    # Footer
    st.markdown("---")
    stats, articles_with_pdfs = st.session_state.harvester.get_stats()
    success_count = stats.get('success', 0)
    
    st.caption(f"🕵️ Shadow Harvester Actif | 📄 {success_count} PDFs téléchargés | 🎯 {articles_with_pdfs} articles avec PDFs | ⚡ Streamlit Cloud")

def _sanitize_dirname(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_\- ]', '_', name).strip().replace(' ', '_') or 'ademe'

if __name__ == "__main__":
    main()