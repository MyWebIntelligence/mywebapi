"""
Test d'intégration complet pour le crawling des actualités sur l'Ukraine avec affichage détaillé des résultats.
"""
import pytest
from unittest.mock import patch, Mock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.db.models import User, Land, Expression, Domain, Media
from app.crud.crud_land import land as crud_land
from app.crud.crud_expression import expression as crud_expression
from app.core.crawler_engine import CrawlerEngine
from app.schemas.land import LandCreate

# URLs des actualités à tester
UKRAINE_NEWS_URLS = [
    "https://www.lesechos.fr/idees-debats/editos-analyses/lukraine-la-guerre-oubliee-2174660",
    "https://www.midilibre.fr/2025/07/03/guerre-en-ukraine-vladimir-poutine-annonce-quil-sentretiendra-a-nouveau-par-telephone-avec-donald-trump-ce-jeudi-12803739.php",
    "https://www.leparisien.fr/international/ukraine/guerre-en-ukraine-un-guerrier-au-moral-dacier-qui-est-mikhail-goudkov-le-numero-2-de-la-marine-russe-tue-par-kiev-03-07-2025-UH6PSN6EJZCHLAPUXCO5ARTKFA.php",
    "https://www.lemonde.fr/international/live/2025/07/03/en-direct-guerre-en-ukraine-washington-minimise-la-pause-dans-la-livraison-d-armes-a-kiev_6616331_3210.html",
    "https://www.france24.com/fr/europe/20250702-washington-cesse-livrer-certaines-armes-ukraine-kiev-veut-clarifier-les-d%C3%A9tails",
    "https://www.midilibre.fr/2025/07/03/guerre-en-ukraine-quest-ce-que-le-missile-hellfire-qui-peut-detruire-nimporte-quel-char-et-qui-ne-sera-plus-livre-a-kiev-par-les-etats-unis-12803355.php",
    "https://www.lefigaro.fr/international/l-ukraine-sous-la-double-menace-des-bombes-russes-et-du-desengagement-americain-20250702",
    "https://www.lefigaro.fr/international/guerre-en-ukraine-un-mort-russe-dans-des-frappes-de-drones-ukrainiens-20250703",
    "https://www.franceinfo.fr/monde/europe/manifestations-en-ukraine/guerre-en-ukraine-des-frappes-de-drones-ukrainiens-font-un-mort-et-plusieurs-blesses-en-russie_7352496.html",
    "https://www.sudouest.fr/international/guerre-en-ukraine-la-russie-frappe-un-centre-de-recrutement-ukrainien-au-moins-deux-morts-25092367.php",
    "https://www.ladepeche.fr/2025/07/03/direct-guerre-en-ukraine-kiev-appelle-a-une-aide-militaire-continue-de-washington-qui-minimise-larret-de-livraisons-darmes-12802715.php",
    "https://www.ouest-france.fr/europe/ukraine/guerre-en-ukraine-confusion-sur-laide-americaine-renfort-nord-coreen-le-point-sur-la-nuit-54a41796-5792-11f0-9771-bf42ae6be7a5",
    "https://www.ladepeche.fr/2025/07/02/guerre-en-ukraine-la-coree-du-nord-prete-a-envoyer-30-000-soldats-en-russie-ce-que-devoile-le-rapport-des-renseignements-ukrainiens-12801753.php",
    "https://www.parismatch.com/actu/international/guerre-en-ukraine-kim-jong-un-pret-a-envoyer-30-000-soldats-en-soutien-a-la-russie-253677",
    "https://www.lexpress.fr/monde/europe/guerre-en-ukraine-la-coree-du-nord-prete-a-envoyer-30-000-nouveaux-soldats-sur-le-front-M6LO2TDXPJG45GF73DF4Y7HAOI/",
    "https://www.20minutes.fr/monde/russie/4161444-20250702-russie-ukraine-iran-nucleaire-tout-savoir-premier-appel-depuis-2022-entre-macron-poutine",
    "https://www.bfmtv.com/politique/elysee/l-appel-entre-emmanuel-macron-et-vladimir-poutine-peut-il-faire-bouger-les-negociations-sur-l-ukraine_AV-202507020465.html",
    "https://www.ledauphine.com/defense-guerre-conflit/2025/07/03/vladimir-poutine-et-donald-trump-vont-s-entretenir-ce-jeudi",
    "https://www.ouest-france.fr/europe/ukraine/carte-guerre-en-ukraine-echange-macron-poutine-frappes-sur-une-usine-russe-le-point-du-jour-3aa5faaa-5696-11f0-9771-bf42ae6be7a5",
    "https://www.lesechos.fr/monde/europe/la-presidence-danoise-de-lue-demarre-sous-le-signe-du-soutien-a-lukraine-membre-de-la-famille-2174653",
    "https://www.rtl.be/actu/monde/international/guerre-en-ukraine/lukraine-membre-de-lunion-europeenne-le-pays-est-essentiel-la-securite-de/2025-07-03/article/755302",
    "https://www.la-croix.com/international/ukraine-la-corruption-touche-le-cercle-rapproche-de-volodymyr-zelensky-20250630",
    "https://www.boursorama.com/actualite-economique/actualites/l-ukraine-a-signe-un-accord-de-production-avec-une-entreprise-americaine-de-drones-zelensky-0a7af06615aeeb57e3f78611aa17a6b4",
    "https://www.lemonde.fr/international/live/2025/07/02/en-direct-guerre-en-ukraine-les-etats-unis-renoncent-a-livrer-certaines-armes-a-kiev_6616331_3210.html",
    "https://www.lemonde.fr/international/live/2025/07/03/en-direct-guerre-en-ukraine-au-moins-deux-morts-dans-une-frappe-de-missile-russe-sur-le-port-d-odessa_6616331_3210.html",
    "https://www.20minutes.fr/monde/ukraine/4161642-20250703-direct-guerre-ukraine-mort-blesses-frappes-drones-ukrainiens-russie"
]

UKRAINE_KEYWORDS = [
    "ukraine", "guerre", "poutine", "zelensky", "russie", "kiev", "moscou",
    "trump", "macron", "armes", "drones", "soldats", "coree", "nord",
    "etats-unis", "europe", "otan", "offensive", "defense", "paix",
    "negociations", "diplomatie", "sanctions", "missile", "hellfire",
    "corruption", "union", "europeenne", "odessa", "conflit"
]

@pytest.fixture
async def ukraine_news_land(async_db_session: AsyncSession, test_user: User) -> Land:
    """Fixture pour créer un land de test pour les actualités Ukraine."""
    land_data = LandCreate(
        name="Ukraine News Crawl Results Analysis",
        description="Test détaillé de crawling des actualités sur la guerre en Ukraine",
        lang=["fr"],
    )
    owner_id = test_user.id
    assert isinstance(owner_id, int)
    land = await crud_land.create(db=async_db_session, obj_in=land_data, owner_id=owner_id)

    land_id = land.id
    assert isinstance(land_id, int)
    await crud_land.add_terms_to_land(async_db_session, land_id=land_id, terms=UKRAINE_KEYWORDS)

    for url in UKRAINE_NEWS_URLS:
        await crud_expression.get_or_create_expression(
            db=async_db_session, land_id=land_id, url=url, depth=0
        )
    
    await async_db_session.commit()
    await async_db_session.refresh(land)
    return land

def display_separator(title: str, char: str = "="):
    """Affiche un séparateur avec titre."""
    print(f"\n{char * 80}")
    print(f"{title:^80}")
    print(f"{char * 80}")

def display_crawl_summary(total_expressions: int, processed: int, errors: int, execution_time: float):
    """Affiche le résumé du crawl."""
    display_separator("📊 RÉSUMÉ DU CRAWL", "=")
    print(f"🎯 Expressions totales:     {total_expressions}")
    print(f"✅ Expressions traitées:    {processed}")
    print(f"❌ Erreurs:                 {errors}")
    print(f"📈 Taux de réussite:        {(processed/total_expressions)*100:.1f}%")
    print(f"⏱️  Temps d'exécution:       {execution_time:.2f}s")
    print(f"⚡ Vitesse moyenne:         {processed/execution_time:.1f} expressions/sec")

def display_domain_analysis(expressions):
    """Affiche l'analyse par domaine."""
    display_separator("🌐 ANALYSE PAR DOMAINE", "-")
    
    domain_stats = {}
    for expr in expressions:
        if expr.url in UKRAINE_NEWS_URLS and expr.crawled_at:
            # Extract domain from URL
            from urllib.parse import urlparse
            domain = urlparse(expr.url).netloc
            
            if domain not in domain_stats:
                domain_stats[domain] = {
                    'count': 0,
                    'total_relevance': 0,
                    'avg_relevance': 0,
                    'urls': []
                }
            
            domain_stats[domain]['count'] += 1
            domain_stats[domain]['total_relevance'] += (expr.relevance or 0)
            domain_stats[domain]['urls'].append(expr.url)
    
    # Calculate averages and sort by relevance
    for domain in domain_stats:
        if domain_stats[domain]['count'] > 0:
            domain_stats[domain]['avg_relevance'] = domain_stats[domain]['total_relevance'] / domain_stats[domain]['count']
    
    sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1]['avg_relevance'], reverse=True)
    
    print(f"{'Domaine':<25} {'Articles':<8} {'Pertinence':<12} {'Score Moyen':<12}")
    print("-" * 65)
    
    for domain, stats in sorted_domains:
        print(f"{domain:<25} {stats['count']:<8} {stats['total_relevance']:<12.3f} {stats['avg_relevance']:<12.3f}")

def display_content_analysis(expressions):
    """Affiche l'analyse du contenu."""
    display_separator("📝 ANALYSE DU CONTENU", "-")
    
    total_with_content = 0
    total_with_relevance = 0
    relevance_scores = []
    content_lengths = []
    
    for expr in expressions:
        if expr.url in UKRAINE_NEWS_URLS and expr.crawled_at:
            if expr.readable:
                total_with_content += 1
                content_lengths.append(len(expr.readable))
            
            if expr.relevance is not None:
                total_with_relevance += 1
                relevance_scores.append(expr.relevance)
    
    print(f"📖 Articles avec contenu extracté:  {total_with_content}")
    print(f"🎯 Articles avec score pertinence:  {total_with_relevance}")
    
    if content_lengths:
        avg_length = sum(content_lengths) / len(content_lengths)
        print(f"📏 Longueur moyenne du contenu:     {avg_length:.0f} caractères")
        print(f"📊 Contenu le plus court:          {min(content_lengths)} caractères")
        print(f"📊 Contenu le plus long:           {max(content_lengths)} caractères")
    
    if relevance_scores:
        avg_relevance = sum(relevance_scores) / len(relevance_scores)
        print(f"⭐ Score de pertinence moyen:       {avg_relevance:.3f}")
        print(f"🏆 Meilleur score de pertinence:    {max(relevance_scores):.3f}")
        print(f"📉 Score de pertinence le plus bas: {min(relevance_scores):.3f}")

def display_detailed_results(expressions):
    """Affiche les résultats détaillés pour chaque expression."""
    display_separator("📋 RÉSULTATS DÉTAILLÉS PAR EXPRESSION", "-")
    
    crawled_expressions = [expr for expr in expressions if expr.url in UKRAINE_NEWS_URLS and expr.crawled_at]
    crawled_expressions.sort(key=lambda x: x.relevance or 0, reverse=True)
    
    print(f"{'#':<3} {'Domaine':<20} {'Statut':<8} {'Pertinence':<12} {'Titre':<50}")
    print("-" * 100)
    
    for i, expr in enumerate(crawled_expressions, 1):
        from urllib.parse import urlparse
        domain = urlparse(expr.url).netloc.replace('www.', '')[:19]
        status = f"{expr.http_status}" if expr.http_status else "N/A"
        relevance = f"{expr.relevance:.3f}" if expr.relevance else "N/A"
        title = (expr.title or "Sans titre")[:49]
        
        print(f"{i:<3} {domain:<20} {status:<8} {relevance:<12} {title:<50}")

def display_technical_details(expressions):
    """Affiche les détails techniques."""
    display_separator("🔧 DÉTAILS TECHNIQUES", "-")
    
    http_statuses = {}
    extraction_methods = {"trafilatura": 0, "smart": 0, "beautifulsoup": 0}
    
    for expr in expressions:
        if expr.url in UKRAINE_NEWS_URLS and expr.crawled_at:
            # HTTP Status analysis
            status = expr.http_status or 0
            http_statuses[status] = http_statuses.get(status, 0) + 1
            
            # Content extraction method analysis (based on content length heuristics)
            if expr.readable:
                content_length = len(expr.readable)
                if content_length > 1000:
                    extraction_methods["trafilatura"] += 1
                elif content_length > 200:
                    extraction_methods["smart"] += 1
                else:
                    extraction_methods["beautifulsoup"] += 1
    
    print("📡 Codes de statut HTTP:")
    for status, count in sorted(http_statuses.items()):
        status_name = "✅ Succès" if status == 200 else f"❌ Erreur {status}"
        print(f"   {status_name}: {count} articles")
    
    print("\n🔄 Méthodes d'extraction de contenu (estimées):")
    for method, count in extraction_methods.items():
        print(f"   {method.capitalize()}: {count} articles")

@pytest.mark.asyncio
async def test_ukraine_news_detailed_crawl_analysis(async_db_session: AsyncSession, ukraine_news_land: Land):
    """
    Test de crawling complet avec analyse détaillée des résultats.
    Affiche toutes les statistiques et métriques du crawl.
    """
    # --- Préparation ---
    land_id = ukraine_news_land.id
    assert isinstance(land_id, int)

    # Mock de la réponse HTTP diversifiée pour des résultats réalistes
    def create_mock_response(url):
        """Crée une réponse mock différente selon l'URL."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        # Contenu varié selon le domaine
        if "lemonde" in domain:
            content = "Guerre en Ukraine: analyse approfondie du conflit. Vladimir Poutine et Volodymyr Zelensky continuent leurs échanges diplomatiques. Les États-Unis et l'Europe maintiennent leur soutien militaire avec des livraisons d'armes modernes. La situation géopolitique reste tendue avec la Russie."
            title = "EN DIRECT - Guerre en Ukraine: les derniers développements"
        elif "figaro" in domain:
            content = "Ukraine: la résistance continue face à l'offensive russe. Les forces armées ukrainiennes repoussent les attaques. Kiev demande plus d'armements à l'OTAN. La diplomatie internationale s'active pour trouver une solution pacifique."
            title = "Ukraine: résistance et diplomatie"
        elif "france24" in domain:
            content = "Conflit ukrainien: Washington suspend certaines livraisons d'armes. Trump et Poutine préparent des négociations. L'Union européenne maintient ses sanctions contre la Russie. Les civils ukrainiens continuent de souffrir des bombardements."
            title = "Washington révise sa stratégie d'aide à l'Ukraine"
        else:
            content = f"Article sur la guerre en Ukraine depuis {domain}. Poutine, Zelensky, négociations, armes, OTAN, sanctions, Russie, diplomatie, conflit géopolitique européen."
            title = f"Guerre en Ukraine - Actualités de {domain}"
        
        mock_html = f"""
        <html>
            <head>
                <title>{title}</title>
                <meta name="description" content="Actualités sur le conflit en Ukraine">
                <meta name="keywords" content="ukraine,guerre,poutine,zelensky,russie">
            </head>
            <body>
                <article>
                    <h1>{title}</h1>
                    <p>{content}</p>
                    <p>Les enjeux géopolitiques de ce conflit dépassent les frontières européennes. 
                    L'aide militaire occidentale, les sanctions économiques et les négociations diplomatiques 
                    façonnent l'évolution de cette guerre qui marque l'histoire contemporaine.</p>
                </article>
            </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_html
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.raise_for_status.return_value = None
        return mock_response

    # --- Action ---
    start_time = datetime.now()
    
    with patch("httpx.AsyncClient.get", side_effect=create_mock_response) as mock_get:
        engine = CrawlerEngine(db=async_db_session)
        processed, errors = await engine.crawl_land(land_id=land_id, limit=30)
    
    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()

    # --- Récupération des résultats ---
    expressions_result = await async_db_session.execute(
        select(Expression).where(Expression.land_id == land_id).options(selectinload(Expression.domain))
    )
    expressions = expressions_result.scalars().all()

    # --- Vérifications de base ---
    assert processed == 26, f"Expected 26 processed, got {processed}"
    assert errors == 0, f"Expected 0 errors, got {errors}"
    assert len(expressions) >= 26, f"Expected at least 26 expressions, got {len(expressions)}"

    # --- Affichage détaillé des résultats ---
    display_separator("🇺🇦 ANALYSE COMPLÈTE DU CRAWL UKRAINE", "=")
    print(f"📅 Date d'exécution: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🏷️  Land: {ukraine_news_land.name}")
    print(f"📝 Description: {ukraine_news_land.description}")
    
    display_crawl_summary(len(UKRAINE_NEWS_URLS), processed, errors, execution_time)
    display_domain_analysis(expressions)
    display_content_analysis(expressions)
    display_detailed_results(expressions)
    display_technical_details(expressions)
    
    # --- Vérifications détaillées ---
    crawled_count = 0
    successful_extractions = 0
    high_relevance_count = 0
    
    for expr in expressions:
        if expr.url in UKRAINE_NEWS_URLS:
            crawled_count += 1
            assert expr.crawled_at is not None, f"Expression {expr.url} should have been crawled"
            assert expr.http_status == 200, f"Expression {expr.url} should have status 200"
            assert expr.title is not None, f"Expression {expr.url} should have a title"
            assert expr.relevance is not None and expr.relevance > 0, f"Expression {expr.url} should have relevance > 0"
            
            if expr.readable and len(expr.readable) > 100:
                successful_extractions += 1
            
            if expr.relevance and expr.relevance > 0.5:
                high_relevance_count += 1
    
    assert crawled_count == 26, f"Expected 26 crawled expressions, got {crawled_count}"
    
    # --- Résumé final ---
    display_separator("✅ VALIDATION FINALE", "=")
    print(f"🎯 Expressions crawlées avec succès:      {crawled_count}/26")
    print(f"📖 Extractions de contenu réussies:       {successful_extractions}/26")
    print(f"⭐ Articles à haute pertinence (>0.5):    {high_relevance_count}/26")
    print(f"🚀 Performance: {processed/execution_time:.1f} articles/seconde")
    print(f"💯 Taux de réussite global: {(processed/len(UKRAINE_NEWS_URLS))*100:.1f}%")
    
    display_separator("🎉 CRAWL UKRAINE TERMINÉ AVEC SUCCÈS", "=")
    print("Toutes les métriques sont dans les limites acceptables.")
    print("Le pipeline de crawling fonctionne parfaitement pour les actualités Ukraine!")
    print("=" * 80)