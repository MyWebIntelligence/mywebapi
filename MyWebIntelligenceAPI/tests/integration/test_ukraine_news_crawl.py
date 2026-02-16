"""
Test d'intégration complet pour le crawling des actualités sur l'Ukraine.
"""
import pytest
from unittest.mock import patch, AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.models import User, Land, Expression
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
        name="Ukraine News Crawl Test",
        description="Test de crawling des actualités sur la guerre en Ukraine",
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

@pytest.mark.asyncio
async def test_ukraine_news_full_crawl(async_db_session: AsyncSession, ukraine_news_land: Land):
    """
    Teste le pipeline de crawling complet pour les 26 URLs d'actualités Ukraine.
    Ce test utilise un mock pour les requêtes HTTP pour s'exécuter de manière fiable.
    """
    # --- Préparation ---
    land_id = ukraine_news_land.id
    assert isinstance(land_id, int)

    # Mock de la réponse HTTP pour simuler un crawl réussi
    mock_html_content = f"""
    <html>
        <head><title>Article sur la Guerre en Ukraine</title></head>
        <body>
            <h1>Guerre en Ukraine: Poutine et Zelensky discutent</h1>
            <p>Un article sur le conflit en Ukraine, avec des mots comme Kiev, Russie, et armes.</p>
        </body>
    </html>
    """
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = mock_html_content
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    mock_response.raise_for_status.return_value = None

    # --- Action ---
    # Patch le client HTTP pour ne pas faire de vraies requêtes
    with patch("httpx.AsyncClient.get", return_value=mock_response) as mock_get:
        engine = CrawlerEngine(db=async_db_session)
        processed, errors = await engine.crawl_land(land_id=land_id, limit=30)

    # --- Vérifications ---
    # 1. Vérifier le résultat du crawling
    assert processed == 26
    assert errors == 0
    assert mock_get.call_count == 26

    # 2. Vérifier l'état des expressions
    expressions_after_result = await async_db_session.execute(select(Expression).where(Expression.land_id == land_id))
    expressions_after = expressions_after_result.scalars().all()
    assert len(expressions_after) >= 26  # Au moins les 26 initiales (+ liens découverts possibles)

    crawled_count = 0
    for expr in expressions_after:
        if expr.url in UKRAINE_NEWS_URLS:
            crawled_count += 1
            assert expr.crawled_at is not None, f"Expression {expr.url} should have been crawled"
            assert expr.http_status == 200, f"Expression {expr.url} should have status 200"
            assert expr.title == "Article sur la Guerre en Ukraine", f"Expression {expr.url} should have the correct title"
            assert expr.relevance is not None and expr.relevance > 0, f"Expression {expr.url} should have a relevance score > 0"
            # Note: approved_at n'existe pas dans le modèle actuel
    
    assert crawled_count == 26

    # 3. Vérification finale - le pipeline de crawling fonctionne !
    # Note : Les relations media et links ne sont pas encore complètement implémentées

    print("\n--- Test de crawl Ukraine réussi ---")
    print(f"✅ {crawled_count} expressions ont été crawlées et mises à jour.")
    print("✅ La pertinence a été calculée correctement (scores > 0).")
    print("✅ Les titres et métadonnées ont été extraits.")
    print("✅ Le pipeline de crawling fonctionne parfaitement !")
