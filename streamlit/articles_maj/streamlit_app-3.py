# ademe_app.py - CLOUD OPTIMIZED VERSION
import streamlit as st
import sqlite3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import threading
import json
import re

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

class ADEMEArticle:
    def __init__(self, title, theme, link, description, published, emoji):
        self.title = title
        self.theme = theme
        self.link = link
        self.description = description
        self.published = published
        self.emoji = emoji

class ADEMEAutoPublisher:
    def __init__(self, db_path='ademe_articles.db'):
        self.db_path = db_path
        self.theme_emojis = {
            "Agriculture, alimentation, forêt, bioéconomie": "🌱",
            "Air": "💨",
            "Bâtiment": "🏢", 
            "Changement climatique": "🌡️",
            "Consommer autrement": "🛒",
            "Économie circulaire et Déchets": "♻️",
            "Énergies": "⚡",
            "Industrie et production durable": "🏭",
            "Institutionnel": "🏛️",
            "Mobilité et transports": "🚗",
            "Recherche et innovation": "🔬",
            "Société et politiques publiques": "👥",
            "Urbanisme, territoires et sols": "🗺️"
        }
        self.init_database()
    
    def init_database(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, theme TEXT, link TEXT UNIQUE,
                description TEXT, published TEXT, emoji TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        self.conn.commit()
    
    def parse_rss_feed(self, feed_url):
        """Custom RSS parser without feedparser dependency"""
        try:
            response = requests.get(feed_url, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            articles = []
            
            # RSS 2.0 format
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                desc_elem = item.find('description')
                pub_elem = item.find('pubDate')
                
                if title_elem is not None and link_elem is not None:
                    title = title_elem.text or 'Sans titre'
                    link = link_elem.text or ''
                    description = desc_elem.text if desc_elem is not None else 'Pas de description disponible.'
                    published = pub_elem.text if pub_elem is not None else 'Date inconnue'
                    
                    # Clean up description
                    description = re.sub('<[^<]+?>', '', description)
                    description = description.strip()
                    
                    articles.append({
                        'title': title,
                        'link': link,
                        'description': description,
                        'published': published
                    })
            
            return articles
        except Exception as e:
            st.sidebar.error(f"Erreur parsing RSS: {e}")
            return []
    
    def fetch_all_articles(self):
        all_articles = []
        for theme, feed_url in FEEDS.items():
            try:
                feed_articles = self.parse_rss_feed(feed_url)
                for article_data in feed_articles[:3]:  # Get 3 most recent
                    article = ADEMEArticle(
                        title=article_data['title'],
                        theme=theme,
                        link=article_data['link'],
                        description=article_data['description'],
                        published=article_data['published'],
                        emoji=self.theme_emojis.get(theme, '📄')
                    )
                    all_articles.append(article)
            except Exception as e:
                st.sidebar.error(f"Erreur {theme}: {e}")
        return all_articles
    
    def update_database(self, articles):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE articles SET is_active = 0")
        for article in articles:
            cursor.execute('''
                INSERT OR REPLACE INTO articles 
                (title, theme, link, description, published, emoji, last_updated, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ''', (article.title, article.theme, article.link, 
                  article.description, article.published, article.emoji, datetime.now()))
        self.conn.commit()
        return len(articles)
    
    def get_active_articles(self, limit=30):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT title, theme, link, description, published, emoji
            FROM articles WHERE is_active = 1
            ORDER BY published DESC LIMIT ?
        ''', (limit,))
        results = cursor.fetchall()
        return [ADEMEArticle(*row) for row in results]
    
    def get_stats(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles WHERE is_active = 1")
        active_count = cursor.fetchone()[0]
        cursor.execute("SELECT MAX(last_updated) FROM articles")
        last_update = cursor.fetchone()[0]
        return active_count, last_update

def run_scheduled_update():
    """Manual scheduler without 'schedule' dependency"""
    try:
        publisher = ADEMEAutoPublisher()
        articles = publisher.fetch_all_articles()
        count = publisher.update_database(articles)
        if 'last_update' in st.session_state:
            st.session_state.last_update = datetime.now()
            st.session_state.article_count = count
        print(f"🔄 Scheduled update: {count} articles")
    except Exception as e:
        print(f"❌ Update failed: {e}")

def start_simple_scheduler():
    """Simple scheduler using threading without external dependencies"""
    def scheduler_loop():
        while True:
            now = datetime.now()
            # Run at 8 AM and 2 PM daily
            if now.hour in [8, 14] and now.minute == 0:
                run_scheduled_update()
            time.sleep(60)  # Check every minute
    
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()

# ==================== STREAMLIT APP ====================
def main():
    st.set_page_config(
        page_title="Guides ADEME Auto",
        page_icon="📚",
        layout="wide"
    )
    
    # Initialize session state
    if 'publisher' not in st.session_state:
        st.session_state.publisher = ADEMEAutoPublisher()
    if 'last_update' not in st.session_state:
        st.session_state.last_update = datetime.now()
    if 'scheduler_started' not in st.session_state:
        start_simple_scheduler()
        st.session_state.scheduler_started = True
    
    # Header
    st.title("📚 Guides ADEME - Mise à jour Automatique")
    st.markdown("*Plateforme automatique des derniers guides ADEME*")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("🛠️ Contrôles")
        
        if st.button("🔄 Mettre à jour Maintenant", use_container_width=True):
            with st.spinner("Mise à jour en cours..."):
                articles = st.session_state.publisher.fetch_all_articles()
                count = st.session_state.publisher.update_database(articles)
                st.session_state.last_update = datetime.now()
                st.success(f"✅ {count} articles mis à jour!")
                st.rerun()
        
        st.markdown("---")
        st.header("📊 Statistiques")
        active_count, last_update = st.session_state.publisher.get_stats()
        st.metric("Articles Actifs", active_count)
        if last_update:
            st.metric("Dernière Màj", last_update.split()[0] if isinstance(last_update, str) else str(last_update)[:10])
        
        st.markdown("---")
        st.info("""
        **Fonctionnalités:**
        • Màj auto quotidienne
        • 30 articles récents  
        • Recherche & filtres
        • Interface responsive
        """)
    
    # Main content
    articles = st.session_state.publisher.get_active_articles(30)
    
    if not articles:
        st.warning("Aucun article disponible. Cliquez sur 'Mettre à jour' pour charger les articles.")
        return
    
    # Search and filters
    col1, col2 = st.columns([2, 1])
    with col1:
        search_term = st.text_input("🔍 Rechercher articles", "")
    with col2:
        all_themes = list(set([a.theme for a in articles]))
        selected_themes = st.multiselect("Thèmes", all_themes, default=all_themes, placeholder="Tous les thèmes")
    
    # Filter articles
    filtered_articles = [a for a in articles if a.theme in selected_themes]
    if search_term:
        filtered_articles = [a for a in filtered_articles 
                           if search_term.lower() in a.title.lower() 
                           or search_term.lower() in a.description.lower()]
    
    if not filtered_articles:
        st.warning("Aucun article trouvé avec ces critères.")
        return
    
    # Article selection
    article_titles = [f"{a.emoji} {a.title}" for a in filtered_articles]
    selected_index = st.selectbox("Sélectionnez un article", range(len(article_titles)), 
                                 format_func=lambda x: article_titles[x])
    
    selected_article = filtered_articles[selected_index]
    
    # Article display
    st.markdown("---")
    st.header(f"{selected_article.emoji} {selected_article.title}")
    
    # Metadata
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Thème", selected_article.theme)
    with col2:
        pub_date = selected_article.published
        if 'T' in str(pub_date):
            pub_date = str(pub_date).split('T')[0]
        st.metric("Publication", pub_date)
    with col3:
        st.metric("Source", "ADEME")
    
    # Description
    st.subheader("📝 Description")
    st.write(selected_article.description)
    
    # Actions
    st.subheader("🔗 Actions")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"[📥 Ouvrir l'article ADEME]({selected_article.link})")
    with col2:
        if st.button("📋 Copier le lien", use_container_width=True):
            st.code(selected_article.link, language="text")
    
    # Quick navigation
    st.markdown("---")
    st.subheader("🎯 Navigation Rapide")
    if len(filtered_articles) > 1:
        cols = st.columns(min(4, len(filtered_articles)))
        for i, article in enumerate(filtered_articles[:4]):
            with cols[i % 4]:
                if st.button(f"{article.emoji} {article.title[:25]}...", use_container_width=True, key=f"nav_{i}"):
                    st.session_state.selected_article = i
                    st.rerun()
    
    # Footer
    st.markdown("---")
    st.caption(f"🕒 Dernière mise à jour: {st.session_state.last_update.strftime('%d/%m/%Y %H:%M')} | 📊 {len(articles)} articles disponibles | ⚡ Auto-mise à jour activée")

# Run the app
if __name__ == "__main__":
    main()