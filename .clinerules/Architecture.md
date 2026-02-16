# Architecture de l’API MyWebIntelligence

L’architecture de MyWebIntelligence s’articule en deux parties principales : le client web (_MyWebClient_) et l’API (_MyWebIntelligenceAPI_). Le _client_ est une application React/Node.js (dossier `MyWebClient`) qui sert l’interface utilisateur, tandis que l’_API_ est réalisée en Python avec FastAPI (dossier `MyWebIntelligenceAPI`). L’environnement est orchestré par Docker Compose (voir _docker-compose.yml_[GitHub](docker-compose.yml)[GitHub](docker-compose.yml)) : on y trouve les services **postgres** (base de données PostgreSQL), **redis** (broker de tâches), **mywebintelligenceapi** (API FastAPI), **mywebclient** (client web), un **celery\_worker** (exécutant les tâches asynchrones), un **flower** (monitoring Celery), ainsi que **Prometheus/Grafana** pour la supervision.

Dans l’API, l’organisation suit le schéma classique **FastAPI + SQLAlchemy + Celery**. Le dossier `app/core` contient les configurations et la logique métier centrale (p. ex. `crawler_engine.py`, `content_extractor.py`, `media_processor.py`, `text_processing.py`). Les modèles SQLAlchemy sont dans `app/db/models` (ex. `models.Land`, `models.Expression`, etc.), accompagnés de schémas Pydantic dans `app/schemas`. Les opérations CRUD sur la base sont implémentées dans `app/crud/` (ex. `crud_land.py`, `crud_expression.py`, `crud_media.py`, `crud_job.py`). Les **endpoints REST** sont définis sous `app/api/v1/endpoints/` (par ex. `lands.py`, `expressions.py`, `jobs.py`), exposant la gestion des lands, expressions, utilisateurs, tâches, etc. (login/authentification, CRUD de Land, lancement de crawl, etc.).

Les **dépendances internes** incluent notamment l’accès à la BD via SQLAlchemy (avec PostgreSQL), l’envoi de requêtes HTTP asynchrones via `httpx` ou `aiohttp`, et les calculs via des bibliothèques NLP (NLTK), de traitement d’image (Pillow, scikit-learn) et de scraping (BeautifulSoup, Trafilatura, Newspaper, readability). Externes, on trouve la gestion de l’authentification (JWT via python-jose), la manipulation d’images (ImageHash, ColorThief), l’archivage (archive.org via `internetarchive`), etc. Un exemple de configuration Docker liste ces technologies clés dans _requirements.txt_[GitHub](MyWebIntelligenceAPI/requirements.txt).

Les **points d’entrée API** comprennent au moins les routes suivantes (extraits des endpoints) :

- **`/api/v1/lands`** : CRUD des « lands » (projets d’analyse), création et listing des lands pour l’utilisateur courant[GitHub](MyWebIntelligenceAPI/app/api/v1/endpoints/lands.py)[GitHub](MyWebIntelligenceAPI/app/api/v1/endpoints/lands.py).
    
- **`/api/v1/lands/{land_id}/crawl`** : lance en tâche asynchrone un crawl pour le land donné (via Celery)[GitHub](MyWebIntelligenceAPI/app/api/v1/endpoints/lands.py)[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py).
    
- **`/api/v1/lands/{land_id}/consolidate`** : lance la consolidation des données d’un land[GitHub](MyWebIntelligenceAPI/app/api/v1/endpoints/lands.py).
    
- **`/api/v1/expressions`** (probablement) : accès aux expressions collectées (CRUD, filtrage, pagination) – en cours d’implémentation.
    
- **`/api/v1/jobs`** : suivi des tâches de crawling/consolidation (status, annulation, historique).
    

La base de données interne contient des entités telles que _Land_ (projet thématique), _Expression_ (URL analysée), _ExpressionLink_ (arêtes entre pages), _Media_ (média/image extraits), _Word/LandDictionary_ (pour le scoring), ainsi qu’un modèle _CrawlJob_ pour tracer l’état des tâches (créé par `crud_job.create`)[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py)[GitHub](MyWebIntelligenceAPI/app/crud/crud_job.py).

En résumé, l’architecture technique est la suivante :

- **Front-end** : React + Bootstrap pour l’UI, packagé via Node.js (MyWebClient)[GitHub](MyWebClient/client/src/index.js).
    
- **Back-end API** : FastAPI (Python) exposant des endpoints REST, utilisant SQLAlchemy (PostgreSQL) pour la persistance. Les requêtes HTTP (crawling) sont gérées en async via `httpx`. Les données extraites sont stockées en BD et accessibles via l’API.
    
- **Workers asynchrones** : tâches Celery (broker Redis) pour exécuter les crawls et consolidations en arrière-plan[GitHub](MyWebIntelligenceAPI/app/core/celery_app.py)[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py). Chaque tâche crée un _job_ en base et met à jour le statut du land (RUNNING, COMPLETED, FAILED).
    
- **Base de données** : PostgreSQL. Les modèles incluent Land, Expression, Domain, Media, Word, LandDictionary, CrawlJob, etc. (Cf. README et code)[GitHub](.crawlerOLD_APP/model.py)[GitHub](MyWebIntelligenceAPI/app/crud/crud_job.py).
    
- **Monitoring** : Prometheus (via starlette-prometheus) et Grafana pour la collecte de métriques système/API.
    
- **Dépendances** : Voir _requirements.txt_[GitHub](MyWebIntelligenceAPI/requirements.txt), notamment FastAPI/Uvicorn, SQLAlchemy, Celery, Redis, httpx, Trafilatura, BeautifulSoup, Pillow, scikit-learn, etc.
    

En pratique, l’application se déploie via `docker-compose up`, qui démarre ces conteneurs interconnectés[GitHub](docker-compose.yml)[GitHub](docker-compose.yml). L’API écoute sur le port 8000, et le client sur le port 3002. Les services intérieurs collaborent ainsi pour fournir l’ensemble des fonctionnalités de crawling, traitement et restitution.

# Pipelines fonctionnels

Les pipelines de traitement implémentés suivent principalement les étapes de _crawling_ de pages Web, d’extraction de contenu, d’enrichissement (liens, médias, scoring) et de **restauration via l’API**. Les principaux sont :

- ## Pipeline de Crawling
    
    Cette pipeline parcourt les URL (« expressions ») d’un land et les analyse. L’ordre d’exécution est :
    
    1. **Sélection des expressions à crawler** : la tâche Celery appelle `CrawlingService.crawl_land_directly(land_id)`[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py). Celui-ci récupère les _expressions_ non encore traitées via `crud_expression.get_expressions_to_crawl` (filtrant par land, statut HTTP, profondeur, etc.)[GitHub](MyWebIntelligenceAPI/app/crud/crud_expression.py).
        
    2. **Traitement de chaque expression** : pour chaque URL, `CrawlerEngine.crawl_expression(expr, ...)` est exécuté[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py). Cette méthode :
        
        - Effectue la requête HTTP asynchrone pour récupérer le HTML brut (via `http_client.get`) – en gérant le _User-Agent_ et timeout (cf. `crawler_engine.py`, section HTTP).
            
        - Si l’accès direct échoue, tente d’obtenir un snapshot sur Archive.org, ou en dernier recours une requête directe (cf. pipeline en commentaire dans le code _core.py_ historique). Le code actuel assure déjà une seule tentative avec httpx, mais la logique d’Archive.org peut être intégrée.
            
        - Appelle `get_readable_content(html)`[GitHub](MyWebIntelligenceAPI/app/core/content_extractor.py) pour extraire le texte lisible. Ce code utilise _Trafilatura_ en priorité (extraction propre de texte) et, si Trafilatura ne donne pas assez de contenu, retombe sur un nettoyage basique via BeautifulSoup.
            
        - Extrait les métadonnées du HTML (titre, description, mots-clés, langue) via `get_metadata(soup, url)`[GitHub](MyWebIntelligenceAPI/app/core/content_extractor.py).
            
        - Stocke ces informations dans l’objet `expr` (modèle SQLAlchemy) : champ `title`, `description`, `keywords`, `lang`, ainsi que `readable` pour le contenu. Le champ `readable_at` est mis à jour avec l’heure actuelle.
            
        - **Scoring** : calcule la pertinence de la page via `expression_relevance(dictionary, expr)`[GitHub](MyWebIntelligenceAPI/app/core/text_processing.py)[GitHub](MyWebIntelligenceAPI/app/core/text_processing.py). Cette fonction fait du tokenizing/stemming (NLTK) du titre et du contenu, puis compte les occurrences pondérées des lemmes du _dictionnaire du land_. Le score obtenu (int) est stocké dans `expr.relevance`.
            
        - Si le score est positif (>0), on considère la page « approuvée » et on met à jour `expr.approved_at`.
            
        - **Extraction de liens et médias** :
            
            - Pour les médias : `CrawlerEngine._extract_media(soup, expr)` collecte toutes les URLs d’images/vidéos dans la page (balises `<img>`, `<video>`, etc.), normalise les URLs, puis pour chaque URL appelle `MediaProcessor.analyze_image(url)`[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py). Cette analyse asynchrone télécharge l’image (via `httpx`), calcule un hash (SHA256), lit ses dimensions et format (via Pillow), détecte la transparence, et (si activé) calcule les couleurs dominantes via _KMeans_ (sklearn) et les convertit en couleurs _web-safe_[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py)[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py)[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py). Les métadonnées EXIF basiques sont également extraites. Le résultat (dict) est stocké en base via `crud_media.create_media(...)`.
                
            - Pour les liens : `CrawlerEngine._extract_links(soup, expr)` cherche tous les `<a>` dans la page. Pour chaque URL cible, on vérifie si elle est « crawlable » (commence par http/https et n’est pas un type de fichier exclu). Si oui, on obtient ou crée une `Expression` correspondante (`crud_expression.get_or_create_expression(db, land_id, url, depth)`) et on crée un lien `ExpressionLink(source=expr, target=new_expr)` pour maintenir le graphe[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py).
                
        - Chaque expression est validée et `db.commit()` est fait pour sauvegarder tous ces changements (métadonnées, contenu, médias, liens).
            
        - Le résultat de `crawl_expression` est comptabilisé (succès ou erreur).
            
    
    Au final, la tâche Celery `crawl_land_task` renvoie le nombre de pages traitées et d’erreurs[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py). Elle met aussi à jour le statut du land en base (RUNNING, puis COMPLETED/FAILED) via `crud_land.update_land_status`[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py).
    
- ## Pipeline de Consolidation
    
    Ce pipeline réévalue les expressions déjà crawlées pour recalculer leur pertinence et re-extraire liens et médias à partir du contenu stocké. Déclenché par `consolidate_land_task` ou l’endpoint `POST /lands/{id}/consolidate`. Les étapes principales :
    
    1. Récupération du dictionnaire du land et des expressions déjà crawlées (non-null `fetched_at`) via `crud_expression.get_expressions_to_consolidate` (avec éventuellement filtre par profondeur/limite).
        
    2. Pour chaque `expr` extrait :
        
        - Recalcule le score de pertinence via `expression_relevance` (idéalement avec le même dictionnaire) et met à jour `expr.relevance` si besoin.
            
        - Parcourt `expr.readable` (le HTML « lisible » déjà stocké) avec BeautifulSoup. Puis ré-extrait **liens** (`_extract_and_save_links`) et **médias** (`_extract_and_save_media`) exactement comme dans le crawl initial[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py). On supprime d’abord les anciennes entrées de liens/médias pour cette expression, puis on recrée depuis le contenu mis en cache.
            
        - Commit en base.
            
    
    Ce pipeline permet par exemple d’appliquer de nouveaux critères (mise à jour du dictionnaire, changement de profondeur) aux expressions existantes. Il maintient à jour le graphe de liens et les médias associés, et remplit les champs de pertinence qui peuvent avoir changé. Au retour, on obtient à nouveau un tuple (traités, erreurs)[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py)[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py).
    
- ## Extraction et Enrichissement
    
    - **Extraction de contenu (« readable »)** : pour chaque page crawlée, le pipeline utilise _Trafilatura_ pour obtenir le texte principal, ou en tombe-backs sur BeautifulSoup si nécessaire (cf. `get_readable_content`[GitHub](MyWebIntelligenceAPI/app/core/content_extractor.py)). Les métadonnées HTML (titre, description, keywords, langue) sont extraites par `get_metadata`[GitHub](MyWebIntelligenceAPI/app/core/content_extractor.py). Ces opérations constituent le cœur de l’« extraction readable ».
        
    - **Analyse média** : déjà décrite ci-dessus dans le crawling. Pour chaque image, `MediaProcessor` génère un rapport complet (dimensions, format, hash, couleurs dominantes, EXIF)[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py). Tous ces attributs sont persistés en BD (modèle `Media`) pour chaque URL d’image.
        
    - **Scoring / Pertinence** : la fonction `expression_relevance` (dans `text_processing.py`) réalise le tokenizing/stemming avec NLTK pour français puis compte les occurrences des lemmes du dictionnaire du land (poids 10 pour le titre, 1 pour le contenu)[GitHub](MyWebIntelligenceAPI/app/core/text_processing.py). Elle retourne un score entier stocké dans l’expression, influençant l’autorisation de la page (« approved\_at »).
        
- ## Restitution via l’API
    
    Après traitement, les résultats peuvent être interrogés par l’API. Les endpoints exposent les données ainsi traitées – par exemple, un GET sur `/lands/{id}` renvoie les métadonnées du land avec ses expressions associées, incluant pour chaque page son titre, url, score, date de crawl, etc. D’autres endpoints permettront d’accéder aux liens (relations entre expressions) et médias, ou de déclencher l’export de données. L’API ne comprend pas de front-end de rendu : la restitution s’effectue via JSON (par ex. listes d’expressions) que le _client_ React affichera.
    
    Le lancement de chaque pipeline se fait généralement par un appel à l’API qui démarre une tâche Celery (par exemple `POST /lands/{id}/crawl` crée un _CrawlJob_ en base et renvoie un job\_id[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py)). Le suivi s’effectue via l’endpoint jobs (à implémenter) ou via WebSocket (prévu).
    

# Écarts entre ancienne et nouvelle version

Le répertoire `.crawlerOLD_APP` contient l’ancienne implémentation CLI. Plusieurs fonctionnalités existantes dans l’ancienne version n’ont pas (encore) été réimplémentées dans la version actuelle :

- **Gestion des domaines** : l’ancien code possédait un modèle _Domain_ et un contrôleur `DomainController` qui permettaient de crawler séparément les homepages des domaines référencés (avec statuts HTTP, métadonnées de domaine)[GitHub](.crawlerOLD_APP/core.py). La version actuelle n’a pas d’équivalent : il n’existe pas d’endpoint ni de modèle _Domain_ géré (le modèle existe en BD, mais aucun endpoint public ni tâche n’y fait référence). Il manquerait la logique de `crawl_domains()` qui alimentait la table Domain ainsi que la mise à jour heuristique (`update_heuristic()`) qui synchronisait les noms de domaines des expressions. Cela a pour impact qu’aucune information sur les domaines (http\_status, titre du site, etc.) n’est collectée actuellement.
    
- **Tagging et catégories de contenu** : l’ancienne version comportait un modèle `Tag` et `TaggedContent`, ainsi qu’un `TagController` pour exporter des tags (types « matrix » ou « content »)[GitHub](.crawlerOLD_APP/controller.py). Rien de semblable n’existe dans la nouvelle API. Or l’ancien pipeline Média pré-calculait également des « content\_tags » et un « nsfw\_score » pour chaque image (colonnes `Media.content_tags` et `Media.nsfw_score`[GitHub](.crawlerOLD_APP/model.py)[GitHub](.crawlerOLD_APP/model.py)). Ces champs ne sont pas pris en charge dans le code Python actuel. Pour reproduire entièrement l’ancienne application, il faudrait implémenter l’analyse de contenu des images (reconnaissance de labels ou détection NSFW) et les stocker, ainsi qu’un mécanisme de génération de tags à partir des textes/pages.
    
- **Pipeline Mercury (readable pipeline)** : l’ancienne version offrait un pipeline `MercuryReadablePipeline` (fichier _readable\_pipeline.py_) qui utilisait l’outil Mercury Parser pour extraire de manière enrichie et fusionner les contenus (« smart merge », etc.)[GitHub](.crawlerOLD_APP/readable_pipeline.py)[GitHub](.crawlerOLD_APP/readable_pipeline.py). Cette logique avancée de lecture de pages, incluant fusion intelligente et traitement batch, n’est pas présente dans la nouvelle API. À la place, seul Trafilatura/BS est utilisé via `content_extractor.py`. Reprendre le pipeline Mercury (avec ses stratégies de fusion de champs) pourrait améliorer la qualité de l’extraction de contenu si nécessaire.
    
- **Export de données** : l’ancienne application proposait des exports complets via la classe `Export` (formats CSV, GEXF, etc.) – par exemple les commandes `land export` ou `tag export` appelaient `core.export_land()` et `core.export_tags()` pour créer des fichiers dans `settings.data_location`[GitHub](.crawlerOLD_APP/core.py)[GitHub](.crawlerOLD_APP/core.py). La nouvelle API ne contient pas ces fonctionnalités d’export (les endpoints correspondants ne sont pas encore implémentés). Il manque donc l’équivalent de ces exports, que l’on retrouverait dans un futur `export_task` ou endpoint `/export`.
    
- **Analyse des médias (hors visuels)** : dans l’ancien code, `MediaAnalyzer` permettait d’analyser séquentiellement tous les médias existants d’un land[GitHub](.crawlerOLD_APP/controller.py). Il gérait notamment le téléchargement des images et stockait la date d’analyse, les erreurs, etc. Aujourd’hui, l’analyse d’image est exécutée _dans_ le pipeline de crawling (MediaProcessor) et les métadonnées sont directement écrites. Cependant, les fonctionnalités facultatives (filtrage par taille minimale, nombre de couleurs, etc.) sont reproduites en partie. Il reste à vérifier des options comme les retries ou timeouts du downloader, ainsi que les critères de taille (les settings YAML ne sont pas exposés pour le moment).
    
- **Mise à jour heuristique** : l’ancien script inclut `core.update_heuristic()`, qui parcourait toutes les expressions et recalculait leur domaine (via `get_domain_name`), afin de migrer une expression vers un nouvel enregistrement `Domain` si le nom différait[GitHub](.crawlerOLD_APP/core.py). Cet utilitaire n’existe pas dans la nouvelle codebase. Son absence implique que si un URL a été rattaché initialement au mauvais domaine, cela n’est pas corrigé automatiquement.
    
- **Contrôleur Land avancé** : des commandes CLI comme `land addterm` et `land addurl` permettaient d’ajouter manuellement des termes au dictionnaire du land ou des URL en lot[GitHub](.crawlerOLD_APP/controller.py)[GitHub](.crawlerOLD_APP/controller.py). Dans l’API actuelle, l’ajout de termes au dictionnaire n’est pas encore exposé (pas d’endpoint `/lands/{id}/addterm` par défaut), et l’ajout d’expressions se fait implicitement via crawl et lien(s). Pour une fonctionnalité équivalente, on pourrait prévoir un endpoint pour injecter des termes ou URL manuellement.
    
- **Stratégies avancées de crawling** : l’ancienne version gérait des filtres supplémentaires (statut HTTP, limites de pertinence, _robots.txt_, profondeur, recrawl selon status) mentionnés dans le README et les controllers CLI[GitHub](.crawlerOLD_APP/cli.py). Le nouveau code prévoit des paramètres (`limit`, `http`, `depth` dans les endpoints et services), mais certains aspects comme le respect de robots.txt ou un filtrage sur la pertinence minimale ne semblent pas implémentés. Reprendre ces fonctionnalités améliore le contrôle du crawl.
    

En résumé, pour que la nouvelle application soit une réplique complète de l’ancienne, il faudrait réimplémenter notamment **la gestion des domaines**, **la génération et export de tags**, **l’export de données** et **le pipeline de fusion de contenu (Mercury)**. Chacune de ces fonctionnalités manque à l’appel :

- _Export de Land/Tags_ : rôle = permettre d’exporter les données en CSV/GEXF/ZIP, logique = utiliser la classe `Export` de l’ancien code pour formater les graphes et pages (impact : ajout de jobs d’export et endpoints associés).
    
- _Tagging_ : rôle = créer des catégories à partir du contenu crawlé (p. ex. extraire des mots-clés ou labels d’images), logique = importer le schéma `Tag`/`TaggedContent` et les routines de `export_tags()`[GitHub](.crawlerOLD_APP/controller.py)[GitHub](.crawlerOLD_APP/core.py) (impact : enrichissement des médias/expressions avec des tags, nouvelle table en base).
    
- _Update des domaines_ : rôle = corriger les noms de domaines des expressions, logique = reprendre `update_heuristic()`[GitHub](.crawlerOLD_APP/core.py) (impact : cohérence du modèle Domain).
    
- _Pipeline Mercury_ : rôle = extraire plus intelligemment le contenu des pages, logique = intégrer `readable_pipeline.py` dans `core/content_extractor.py`[GitHub](MyWebIntelligenceAPI/.memory/DEVELOPMENT_STATUS.md) (impact : qualité d’extraction potentiellement meilleure).
    
- _Export média complet_ : dans l’ancien, `mediacsv` était un type d’export (pages d’images). Non présent dans le nouveau.
    

Chaque item ci-dessus nécessiterait l’ajout de méthodes/contrôleurs dédiés dans l’API (ou des scripts CLI), ainsi que l’enrichissement des modèles de données si nécessaire. Par exemple, réintroduire la table _Tag_ avec ses champs, ou étendre _Media_ pour les scores de contenu NSFW. Cela impliquera de mettre à jour l’architecture (nouveaux endpoints, nouveaux jobs Celery pour l’export, etc.).

En conclusion, la structure de base (FastAPI + SQLAlchemy + Celery) est en place et correspond bien au système historique, mais certains traitements avancés (tags, exports, heuristiques) restent à implémenter pour atteindre une parité fonctionnelle complète avec l’ancienne version.

**Sources internes** : description de l’architecture et des pipelines basée sur le code du dépôt (notamment _crawler\_engine.py_[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py)[GitHub](MyWebIntelligenceAPI/app/core/crawler_engine.py), _text\_processing.py_[GitHub](MyWebIntelligenceAPI/app/core/text_processing.py), _content\_extractor.py_[GitHub](MyWebIntelligenceAPI/app/core/content_extractor.py), _media\_processor.py_[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py)[GitHub](MyWebIntelligenceAPI/app/core/media_processor.py), _crawling\_task.py_[GitHub](MyWebIntelligenceAPI/app/tasks/crawling_task.py), endpoints _lands.py_[GitHub](MyWebIntelligenceAPI/app/api/v1/endpoints/lands.py), et modèles/contrôleurs anciens[GitHub](.crawlerOLD_APP/model.py)[GitHub](.crawlerOLD_APP/controller.py)). Ces extraits illustrent les fonctions clés des pipelines et les différences structurelles entre les versions.

# Schéma de la base de données PostgreSQL

Voici le schéma actuel de la base de données `mywebintelligence` tel qu'exporté depuis l'instance PostgreSQL active.

```sql
--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13
-- Dumped by pg_dump version 15.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: crawlstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.crawlstatus AS ENUM (
    'PENDING',
    'RUNNING',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
);


ALTER TYPE public.crawlstatus OWNER TO postgres;

--
-- Name: mediatype; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.mediatype AS ENUM (
    'IMAGE',
    'VIDEO',
    'AUDIO',
    'DOCUMENT'
);


ALTER TYPE public.mediatype OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: access_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.access_logs (
    id integer NOT NULL,
    user_id integer NOT NULL,
    ip_address character varying(45),
    user_agent text,
    action character varying(100),
    "timestamp" timestamp with time zone DEFAULT now(),
    success boolean
);


ALTER TABLE public.access_logs OWNER TO postgres;

--
-- Name: access_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.access_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.access_logs_id_seq OWNER TO postgres;

--
-- Name: access_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.access_logs_id_seq OWNED BY public.access_logs.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: crawl_jobs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.crawl_jobs (
    id integer NOT NULL,
    land_id integer NOT NULL,
    job_type character varying(50) NOT NULL,
    parameters json,
    status public.crawlstatus,
    progress double precision,
    current_step character varying(255),
    result_data json,
    error_message text,
    log_data json,
    created_at timestamp with time zone DEFAULT now(),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    worker_id character varying(255),
    celery_task_id character varying(255)
);


ALTER TABLE public.crawl_jobs OWNER TO postgres;

--
-- Name: crawl_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.crawl_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.crawl_jobs_id_seq OWNER TO postgres;

--
-- Name: crawl_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.crawl_jobs_id_seq OWNED BY public.crawl_jobs.id;


--
-- Name: domains; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.domains (
    id integer NOT NULL,
    land_id integer NOT NULL,
    name character varying(255) NOT NULL,
    title text,
    description text,
    keywords text,
    ip_address character varying(45),
    robots_txt text,
    favicon_url text,
    total_expressions integer,
    avg_http_status double precision,
    first_crawled timestamp with time zone,
    last_crawled timestamp with time zone,
    language character varying(10),
    encoding character varying(50)
);


ALTER TABLE public.domains OWNER TO postgres;

--
-- Name: domains_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.domains_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.domains_id_seq OWNER TO postgres;

--
-- Name: domains_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.domains_id_seq OWNED BY public.domains.id;


--
-- Name: exports; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.exports (
    id integer NOT NULL,
    land_id integer NOT NULL,
    created_by integer NOT NULL,
    export_type character varying(50) NOT NULL,
    format_version character varying(20),
    parameters json,
    filename character varying(255) NOT NULL,
    file_path text NOT NULL,
    file_size integer,
    mime_type character varying(100),
    total_records integer,
    compression_ratio double precision,
    status character varying(50),
    error_message text,
    created_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone,
    downloaded_at timestamp with time zone
);


ALTER TABLE public.exports OWNER TO postgres;

--
-- Name: exports_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.exports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.exports_id_seq OWNER TO postgres;

--
-- Name: exports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.exports_id_seq OWNED BY public.exports.id;


--
-- Name: expression_links; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.expression_links (
    id integer NOT NULL,
    source_id integer NOT NULL,
    target_id integer NOT NULL,
    link_text text,
    rel_attributes character varying(255),
    is_dofollow boolean,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.expression_links OWNER TO postgres;

--
-- Name: expression_links_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.expression_links_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.expression_links_id_seq OWNER TO postgres;

--
-- Name: expression_links_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.expression_links_id_seq OWNED BY public.expression_links.id;


--
-- Name: expressions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.expressions (
    id integer NOT NULL,
    land_id integer NOT NULL,
    url text NOT NULL,
    url_hash character varying(64),
    title text,
    description text,
    keywords text,
    lang character varying(10),
    relevance integer,
    readable text,
    raw_content text,
    content_hash character varying(64),
    http_status integer,
    depth integer,
    domain_id integer,
    fetched_at timestamp with time zone,
    approved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.expressions OWNER TO postgres;

--
-- Name: expressions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.expressions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.expressions_id_seq OWNER TO postgres;

--
-- Name: expressions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.expressions_id_seq OWNED BY public.expressions.id;


--
-- Name: land_dictionaries; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.land_dictionaries (
    land_id integer NOT NULL,
    word_id integer NOT NULL,
    weight double precision,
    added_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.land_dictionaries OWNER TO postgres;

--
-- Name: lands; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lands (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    lang character varying(255),
    owner_id integer NOT NULL,
    status character varying(50),
    start_urls json,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    last_crawled_at timestamp with time zone,
    total_expressions integer,
    total_media integer,
    avg_relevance double precision
);


ALTER TABLE public.lands OWNER TO postgres;

--
-- Name: lands_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.lands_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.lands_id_seq OWNER TO postgres;

--
-- Name: lands_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.lands_id_seq OWNED BY public.lands.id;


--
-- Name: media; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.media (
    id integer NOT NULL,
    expression_id integer NOT NULL,
    url text NOT NULL,
    media_type public.mediatype,
    mime_type character varying(100),
    file_size integer,
    width integer,
    height integer,
    duration double precision,
    bitrate integer,
    frame_rate double precision,
    channels integer,
    sample_rate integer,
    alt_text text,
    caption text,
    dominant_color character varying(7),
    phash character varying(16),
    dhash character varying(16),
    chash character varying(128),
    sha256 character varying(64),
    exif_data json,
    is_transparent boolean,
    content_tags json,
    nsfw_score double precision,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.media OWNER TO postgres;

--
-- Name: media_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.media_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.media_id_seq OWNER TO postgres;

--
-- Name: media_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.media_id_seq OWNED BY public.media.id;


--
-- Name: tagged_content; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tagged_content (
    id integer NOT NULL,
    expression_id integer NOT NULL,
    tag_id integer NOT NULL,
    created_by integer NOT NULL,
    from_char integer,
    to_char integer,
    quote text,
    comment text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.tagged_content OWNER TO postgres;

--
-- Name: tagged_content_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tagged_content_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.tagged_content_id_seq OWNER TO postgres;

--
-- Name: tagged_content_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tagged_content_id_seq OWNED BY public.tagged_content.id;


--
-- Name: tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tags (
    id integer NOT NULL,
    land_id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    color character varying(7),
    parent_id integer,
    path character varying(255),
    sorting integer,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.tags OWNER TO postgres;

--
-- Name: tags_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.tags_id_seq OWNER TO postgres;

--
-- Name: tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tags_id_seq OWNED BY public.tags.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(255) NOT NULL,
    hashed_password text NOT NULL,
    full_name character varying(255),
    is_active boolean,
    is_superuser boolean,
    is_verified boolean,
    role character varying(50),
    created_at timestamp with time zone DEFAULT now(),
    last_login timestamp with time zone,
    login_attempts integer,
    lockout_until timestamp with time zone
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: words; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.words (
    id integer NOT NULL,
    word character varying(255) NOT NULL,
    lemma character varying(255),
    lang character varying(10),
    pos_tag character varying(50),
    frequency double precision
);


ALTER TABLE public.words OWNER TO postgres;

--
-- Name: words_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.words_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.words_id_seq OWNER TO postgres;

--
-- Name: words_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.words_id_seq OWNED BY public.words.id;


--
-- Name: access_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.access_logs ALTER COLUMN id SET DEFAULT nextval('public.access_logs_id_seq'::regclass);


--
-- Name: crawl_jobs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crawl_jobs ALTER COLUMN id SET DEFAULT nextval('public.crawl_jobs_id_seq'::regclass);


--
-- Name: domains id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.domains ALTER COLUMN id SET DEFAULT nextval('public.domains_id_seq'::regclass);


--
-- Name: exports id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.exports ALTER COLUMN id SET DEFAULT nextval('public.exports_id_seq'::regclass);


--
-- Name: expression_links id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expression_links ALTER COLUMN id SET DEFAULT nextval('public.expression_links_id_seq'::regclass);


--
-- Name: expressions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expressions ALTER COLUMN id SET DEFAULT nextval('public.expressions_id_seq'::regclass);


--
-- Name: lands id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lands ALTER COLUMN id SET DEFAULT nextval('public.lands_id_seq'::regclass);


--
-- Name: media id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media ALTER COLUMN id SET DEFAULT nextval('public.media_id_seq'::regclass);


--
-- Name: tagged_content id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tagged_content ALTER COLUMN id SET DEFAULT nextval('public.tagged_content_id_seq'::regclass);


--
-- Name: tags id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tags ALTER COLUMN id SET DEFAULT nextval('public.tags_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: words id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.words ALTER COLUMN id SET DEFAULT nextval('public.words_id_seq'::regclass);


--
-- Name: access_logs access_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.access_logs
    ADD CONSTRAINT access_logs_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: crawl_jobs crawl_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crawl_jobs
    ADD CONSTRAINT crawl_jobs_pkey PRIMARY KEY (id);


--
-- Name: domains domains_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_pkey PRIMARY KEY (id);


--
-- Name: exports exports_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.exports
    ADD CONSTRAINT exports_pkey PRIMARY KEY (id);


--
-- Name: expression_links expression_links_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expression_links
    ADD CONSTRAINT expression_links_pkey PRIMARY KEY (id);


--
-- Name: expressions expressions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expressions
    ADD CONSTRAINT expressions_pkey PRIMARY KEY (id);


--
-- Name: land_dictionaries land_dictionaries_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.land_dictionaries
    ADD CONSTRAINT land_dictionaries_pkey PRIMARY KEY (land_id, word_id);


--
-- Name: lands lands_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lands
    ADD CONSTRAINT lands_pkey PRIMARY KEY (id);


--
-- Name: media media_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_pkey PRIMARY KEY (id);


--
-- Name: tagged_content tagged_content_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tagged_content
    ADD CONSTRAINT tagged_content_pkey PRIMARY KEY (id);


--
-- Name: tags tags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: words words_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.words
    ADD CONSTRAINT words_pkey PRIMARY KEY (id);


--
-- Name: ix_access_logs_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_access_logs_id ON public.access_logs USING btree (id);


--
-- Name: ix_access_logs_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_access_logs_user_id ON public.access_logs USING btree (user_id);


--
-- Name: ix_crawl_jobs_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_crawl_jobs_id ON public.crawl_jobs USING btree (id);


--
-- Name: ix_crawl_jobs_land_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_crawl_jobs_land_id ON public.crawl_jobs USING btree (land_id);


--
-- Name: ix_crawl_jobs_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_crawl_jobs_status ON public.crawl_jobs USING btree (status);


--
-- Name: ix_domains_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_domains_id ON public.domains USING btree (id);


--
-- Name: ix_domains_land_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_domains_land_id ON public.domains USING btree (land_id);


--
-- Name: ix_domains_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_domains_name ON public.domains USING btree (name);


--
-- Name: ix_exports_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_exports_id ON public.exports USING btree (id);


--
-- Name: ix_exports_land_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_exports_land_id ON public.exports USING btree (land_id);


--
-- Name: ix_expression_links_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_expression_links_id ON public.expression_links USING btree (id);


--
-- Name: ix_expression_links_source_target; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_expression_links_source_target ON public.expression_links USING btree (source_id, target_id);


--
-- Name: ix_expressions_approved; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_expressions_approved ON public.expressions USING btree (approved_at);


--
-- Name: ix_expressions_domain_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_expressions_domain_id ON public.expressions USING btree (domain_id);


--
-- Name: ix_expressions_fetched; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_expressions_fetched ON public.expressions USING btree (fetched_at);


--
-- Name: ix_expressions_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_expressions_id ON public.expressions USING btree (id);


--
-- Name: ix_expressions_land_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_expressions_land_id ON public.expressions USING btree (land_id);


--
-- Name: ix_expressions_relevance; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_expressions_relevance ON public.expressions USING btree (relevance);


--
-- Name: ix_expressions_url_hash; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_expressions_url_hash ON public.expressions USING btree (url_hash);


--
-- Name: ix_land_dictionaries_land_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_land_dictionaries_land_id ON public.land_dictionaries USING btree (land_id);


--
-- Name: ix_land_dictionaries_word_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_land_dictionaries_word_id ON public.land_dictionaries USING btree (word_id);


--
-- Name: ix_lands_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_lands_id ON public.lands USING btree (id);


--
-- Name: ix_lands_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_lands_name ON public.lands USING btree (name);


--
-- Name: ix_lands_owner_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_lands_owner_id ON public.lands USING btree (owner_id);


--
-- Name: ix_media_expression_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_media_expression_id ON public.media USING btree (expression_id);


--
-- Name: ix_media_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_media_id ON public.media USING btree (id);


--
-- Name: ix_media_media_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_media_media_type ON public.media USING btree (media_type);


--
-- Name: ix_media_url_hash; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_media_url_hash ON public.media USING btree (url);


--
-- Name: ix_tagged_content_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tagged_content_created ON public.tagged_content USING btree (created_at);


--
-- Name: ix_tagged_content_expression_tag; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tagged_content_expression_tag ON public.tagged_content USING btree (expression_id, tag_id);


--
-- Name: ix_tagged_content_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tagged_content_id ON public.tagged_content USING btree (id);


--
-- Name: ix_tagged_content_positions; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tagged_content_positions ON public.tagged_content USING btree (from_char, to_char);


--
-- Name: ix_tags_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tags_id ON public.tags USING btree (id);


--
-- Name: ix_tags_land_parent; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tags_land_parent ON public.tags USING btree (land_id, parent_id);


--
-- Name: ix_tags_path; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tags_path ON public.tags USING btree (path);


--
-- Name: ix_tags_sorting; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tags_sorting ON public.tags USING btree (land_id, sorting);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: ix_words_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_words_id ON public.words USING btree (id);


--
-- Name: ix_words_lemma; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_words_lemma ON public.words USING btree (lemma);


--
-- Name: ix_words_word; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_words_word ON public.words USING btree (word);


--
-- Name: access_logs access_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.access_logs
    ADD CONSTRAINT access_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: crawl_jobs crawl_jobs_land_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crawl_jobs
    ADD CONSTRAINT crawl_jobs_land_id_fkey FOREIGN KEY (land_id) REFERENCES public.lands(id);


--
-- Name: domains domains_land_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_land_id_fkey FOREIGN KEY (land_id) REFERENCES public.lands(id);


--
-- Name: exports exports_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.exports
    ADD CONSTRAINT exports_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: exports exports_land_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.exports
    ADD CONSTRAINT exports_land_id_fkey FOREIGN KEY (land_id) REFERENCES public.lands(id);


--
-- Name: expression_links expression_links_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expression_links
    ADD CONSTRAINT expression_links_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.expressions(id);


--
-- Name: expression_links expression_links_target_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expression_links
    ADD CONSTRAINT expression_links_target_id_fkey FOREIGN KEY (target_id) REFERENCES public.expressions(id);


--
-- Name: expressions expressions_domain_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expressions
    ADD CONSTRAINT expressions_domain_id_fkey FOREIGN KEY (domain_id) REFERENCES public.domains(id);


--
-- Name: expressions expressions_land_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expressions
    ADD CONSTRAINT expressions_land_id_fkey FOREIGN KEY (land_id) REFERENCES public.lands(id);


--
-- Name: land_dictionaries land_dictionaries_land_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.land_dictionaries
    ADD CONSTRAINT land_dictionaries_land_id_fkey FOREIGN KEY (land_id) REFERENCES public.lands(id);


--
-- Name: land_dictionaries land_dictionaries_word_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.land_dictionaries
    ADD CONSTRAINT land_dictionaries_word_id_fkey FOREIGN KEY (word_id) REFERENCES public.words(id);


--
-- Name: lands lands_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lands
    ADD CONSTRAINT lands_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id);


--
-- Name: media media_expression_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_expression_id_fkey FOREIGN KEY (expression_id) REFERENCES public.expressions(id);


--
-- Name: tagged_content tagged_content_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tagged_content
    ADD CONSTRAINT tagged_content_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: tagged_content tagged_content_expression_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tagged_content
    ADD CONSTRAINT tagged_content_expression_id_fkey FOREIGN KEY (expression_id) REFERENCES public.expressions(id);


--
-- Name: tagged_content tagged_content_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tagged_content
    ADD CONSTRAINT tagged_content_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(id);


--
-- Name: tags tags_land_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_land_id_fkey FOREIGN KEY (land_id) REFERENCES public.lands(id);


--
-- Name: tags tags_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.tags(id);


--
-- PostgreSQL database dump complete
--
```
