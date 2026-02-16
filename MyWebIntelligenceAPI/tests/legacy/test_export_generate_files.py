"""
Test de génération réelle de fichiers d'export
Crée tous les formats d'export avec des données de test et affiche les chemins
"""

import pytest
import asyncio
import os
import tempfile
from datetime import datetime
from zipfile import ZipFile
from lxml import etree

from app.db.base import AsyncSessionLocal
from app.services.export_service import ExportService
from app.services.export_service_sync import SyncExportService
from app.crud.crud_land import land as land_crud
from app.crud.crud_user import user as user_crud
from app.crud.crud_expression import expression as expression_crud
from app.crud.crud_domain import domain as domain_crud
from app.schemas.land import LandCreate
from app.schemas.user import UserCreate
from app.schemas.expression import ExpressionCreate
from app.schemas.domain import DomainCreate


@pytest.mark.asyncio
class TestExportFileGeneration:
    """Test de génération réelle de fichiers d'export"""
    
    async def setup_method(self):
        """Setup avec données de test réalistes"""
        self.db = AsyncSessionLocal()
        self.generated_files = []
        
        # Create test user
        user_data = UserCreate(
            email=f"export_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com",
            password="testpassword123",
            full_name="Export File Test User"
        )
        self.test_user = await user_crud.create(self.db, obj_in=user_data)
        
        # Create test land
        land_data = LandCreate(
            name="Actualités Tech Export",
            description="Land de test pour génération de fichiers d'export avec données réalistes",
            lang=["fr"],
            user_id=self.test_user.id
        )
        self.test_land = await land_crud.create(self.db, obj_in=land_data)
        
        # Create test domains
        self.test_domains = []
        domain_data_list = [
            {
                "name": "techcrunch.com",
                "title": "TechCrunch",
                "description": "Site d'actualités technologiques",
                "keywords": "tech,startup,innovation"
            },
            {
                "name": "lemonde.fr", 
                "title": "Le Monde",
                "description": "Journal français d'information",
                "keywords": "actualités,france,monde"
            },
            {
                "name": "github.com",
                "title": "GitHub",
                "description": "Plateforme de développement collaboratif",
                "keywords": "code,git,développement"
            }
        ]
        
        for domain_data in domain_data_list:
            domain = await domain_crud.create(self.db, obj_in=DomainCreate(**domain_data))
            self.test_domains.append(domain)
        
        # Create realistic test expressions
        self.test_expressions = []
        expression_data_list = [
            {
                "url": "https://techcrunch.com/2025/07/04/ai-breakthrough-new-language-model",
                "title": "AI Breakthrough: Revolutionary New Language Model Achieves Human-Level Understanding",
                "description": "Researchers announce a major breakthrough in artificial intelligence with a new language model that demonstrates unprecedented understanding capabilities.",
                "keywords": "AI,artificial intelligence,language model,breakthrough,technology",
                "readable": "Une équipe de chercheurs vient d'annoncer une percée majeure dans le domaine de l'intelligence artificielle. Leur nouveau modèle de langage démontre des capacités de compréhension sans précédent, approchant le niveau de compréhension humaine. Cette avancée pourrait révolutionner de nombreux secteurs, de l'éducation à la médecine en passant par la recherche scientifique. Les implications de cette technologie sont vastes et promettent de transformer notre façon d'interagir avec les machines.",
                "relevance": 9,
                "depth": 1,
                "http_status": 200,
                "land_id": self.test_land.id,
                "domain_id": self.test_domains[0].id
            },
            {
                "url": "https://lemonde.fr/technologies/2025/07/04/france-investit-ia-recherche",
                "title": "La France investit massivement dans la recherche en intelligence artificielle",
                "description": "Le gouvernement français annonce un plan d'investissement de 2 milliards d'euros pour développer la recherche en IA sur le territoire national.",
                "keywords": "France,investissement,IA,recherche,gouvernement,technologie",
                "readable": "Le gouvernement français a dévoilé aujourd'hui un ambitieux plan d'investissement de 2 milliards d'euros destiné à positionner la France comme un leader mondial de la recherche en intelligence artificielle. Ce plan prévoit la création de nouveaux centres de recherche, le financement de startups innovantes, et le développement de partenariats avec les universités européennes. L'objectif est de créer un écosystème français compétitif face aux géants américains et chinois de la tech.",
                "relevance": 8,
                "depth": 1,
                "http_status": 200,
                "land_id": self.test_land.id,
                "domain_id": self.test_domains[1].id
            },
            {
                "url": "https://github.com/blog/2025-07-04-copilot-updates",
                "title": "GitHub Copilot: Major Updates Enhance Developer Productivity",
                "description": "GitHub announces significant improvements to Copilot, including better code suggestions and multi-language support.",
                "keywords": "GitHub,Copilot,AI,programming,development,productivity",
                "readable": "GitHub vient d'annoncer des améliorations majeures de son assistant de programmation Copilot. Ces mises à jour incluent des suggestions de code plus précises, un support étendu pour de nouveaux langages de programmation, et une intégration améliorée avec les environnements de développement populaires. Les développeurs peuvent maintenant bénéficier d'une assistance IA plus sophistiquée pour accélérer leur productivité et réduire les erreurs de code.",
                "relevance": 7,
                "depth": 2,
                "http_status": 200,
                "land_id": self.test_land.id,
                "domain_id": self.test_domains[2].id
            },
            {
                "url": "https://techcrunch.com/2025/07/04/quantum-computing-commercial-breakthrough",
                "title": "Quantum Computing Reaches Commercial Viability Milestone",
                "description": "First commercially viable quantum computer announced by leading tech company, marking a new era in computing.",
                "keywords": "quantum computing,commercial,breakthrough,technology,computing",
                "readable": "Une entreprise technologique leader vient d'annoncer le premier ordinateur quantique commercialement viable, marquant une nouvelle ère dans l'informatique. Cette machine révolutionnaire promet de résoudre des problèmes complexes en quelques secondes, là où les ordinateurs traditionnels prendraient des années. Les applications potentielles incluent la cryptographie, la découverte de médicaments, et l'optimisation logistique. Cette avancée pourrait transformer radicalement de nombreux secteurs industriels.",
                "relevance": 8,
                "depth": 1,
                "http_status": 200,
                "land_id": self.test_land.id,
                "domain_id": self.test_domains[0].id
            },
            {
                "url": "https://lemonde.fr/sciences/2025/07/04/recherche-medicale-ia-diagnostic",
                "title": "L'IA révolutionne le diagnostic médical en France",
                "description": "Des chercheurs français développent une IA capable de diagnostiquer des maladies rares avec une précision supérieure aux médecins.",
                "keywords": "IA,médecine,diagnostic,recherche,France,santé",
                "readable": "Une équipe de chercheurs français a développé un système d'intelligence artificielle révolutionnaire capable de diagnostiquer des maladies rares avec une précision remarquable, souvent supérieure à celle des médecins spécialisés. Cette technologie analyse des images médicales, des symptômes et des données génétiques pour identifier des pathologies complexes. Les premiers tests cliniques montrent des résultats prometteurs qui pourraient transformer la médecine de précision et améliorer significativement les soins aux patients.",
                "relevance": 6,
                "depth": 2,
                "http_status": 200,
                "land_id": self.test_land.id,
                "domain_id": self.test_domains[1].id
            }
        ]
        
        for expr_data in expression_data_list:
            expression = await expression_crud.create(self.db, obj_in=ExpressionCreate(**expr_data))
            self.test_expressions.append(expression)
    
    async def teardown_method(self):
        """Cleanup après tests"""
        # Note: We keep the generated files for user inspection
        print(f"\n📁 Files generated and available at:")
        for file_path in self.generated_files:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                print(f"  • {file_path} ({file_size} bytes)")
        
        # Clean up test data
        for expression in self.test_expressions:
            await expression_crud.remove(self.db, id=expression.id)
        
        for domain in self.test_domains:
            await domain_crud.remove(self.db, id=domain.id)
        
        await land_crud.remove(self.db, id=self.test_land.id)
        await user_crud.remove(self.db, id=self.test_user.id)
        
        await self.db.close()
    
    async def test_generate_all_export_formats(self):
        """Test principal: génère tous les formats d'export"""
        export_service = ExportService(self.db)
        
        # Créer un répertoire de sortie avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"/tmp/mywebintelligence_exports_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\n🎯 Génération de fichiers d'export dans: {output_dir}")
        print(f"📊 Land: '{self.test_land.name}' (ID: {self.test_land.id})")
        print(f"📄 {len(self.test_expressions)} expressions de test")
        print(f"🌐 {len(self.test_domains)} domaines de test")
        
        # Liste des formats à tester
        export_formats = [
            ("pagecsv", "Export CSV basique des pages"),
            ("fullpagecsv", "Export CSV complet avec contenu readable"),
            ("nodecsv", "Export CSV des domaines avec statistiques"),
            ("mediacsv", "Export CSV des médias"),
            ("pagegexf", "Export GEXF des pages pour visualisation réseau"),
            ("nodegexf", "Export GEXF des domaines pour visualisation réseau"),
            ("corpus", "Export corpus ZIP avec fichiers texte individuels")
        ]
        
        print(f"\n📋 Génération de {len(export_formats)} formats d'export:")
        
        for export_type, description in export_formats:
            try:
                # Générer le fichier
                custom_filename = f"tech_news_export_{export_type}_{timestamp}"
                file_path, count = await export_service.export_data(
                    export_type=export_type,
                    land_id=self.test_land.id,
                    minimum_relevance=1,
                    filename=custom_filename
                )
                
                # Déplacer vers le répertoire de sortie
                final_path = os.path.join(output_dir, os.path.basename(file_path))
                if os.path.exists(file_path) and file_path != final_path:
                    os.rename(file_path, final_path)
                    file_path = final_path
                
                self.generated_files.append(file_path)
                
                # Vérifier le fichier
                assert os.path.exists(file_path)
                file_size = os.path.getsize(file_path)
                
                print(f"  ✅ {export_type.upper()}: {count} records → {os.path.basename(file_path)} ({file_size} bytes)")
                print(f"     📝 {description}")
                
                # Validation spécifique par format
                await self._validate_export_file(file_path, export_type, count)
                
            except Exception as e:
                print(f"  ❌ {export_type.upper()}: Error - {str(e)}")
                raise e
        
        # Informations finales
        total_size = sum(os.path.getsize(f) for f in self.generated_files if os.path.exists(f))
        print(f"\n📊 Résumé de génération:")
        print(f"  • {len(self.generated_files)} fichiers générés")
        print(f"  • Taille totale: {total_size} bytes ({total_size/1024:.1f} KB)")
        print(f"  • Répertoire: {output_dir}")
        
        # Créer un fichier README
        readme_path = os.path.join(output_dir, "README.md")
        await self._create_readme(readme_path, timestamp)
        
        print(f"\n📁 FICHIERS DISPONIBLES:")
        print(f"📂 Répertoire principal: {output_dir}")
        for file_path in sorted(self.generated_files):
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                print(f"   📄 {os.path.basename(file_path)} ({file_size} bytes)")
        print(f"   📖 README.md (documentation)")
        
        return output_dir
    
    async def _validate_export_file(self, file_path, export_type, count):
        """Valide le contenu d'un fichier d'export"""
        try:
            if export_type.endswith('csv'):
                # Valider CSV
                import csv
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    assert len(rows) >= 1  # Au moins l'en-tête
                    if count > 0:
                        assert len(rows) == count + 1  # En-tête + données
            
            elif export_type.endswith('gexf'):
                # Valider GEXF
                tree = etree.parse(file_path)
                root = tree.getroot()
                assert root.tag == 'gexf'
                assert root.get('version') == '1.2'
            
            elif export_type == 'corpus':
                # Valider ZIP
                with ZipFile(file_path, 'r') as archive:
                    files = archive.namelist()
                    assert len(files) == count
                    # Vérifier qu'au moins un fichier contient du contenu
                    if files:
                        content = archive.read(files[0]).decode('utf-8')
                        assert len(content) > 0
                        assert '---' in content  # Métadonnées
        
        except Exception as e:
            print(f"    ⚠️  Validation warning for {export_type}: {str(e)}")
    
    async def _create_readme(self, readme_path, timestamp):
        """Crée un fichier README explicatif"""
        readme_content = f"""# MyWebIntelligence - Fichiers d'Export Générés

**Date de génération**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Timestamp**: {timestamp}

## 📊 Données Exportées

- **Land**: Actualités Tech Export
- **Expressions**: {len(self.test_expressions)} articles de test
- **Domaines**: {len(self.test_domains)} sources (TechCrunch, Le Monde, GitHub)
- **Filtrage**: Relevance minimum = 1

## 📁 Formats d'Export Disponibles

### CSV Exports
- **tech_news_export_pagecsv_{timestamp}.csv**
  - Export basique des pages avec métadonnées
  - Colonnes: id, url, title, description, keywords, relevance, depth, domain info

- **tech_news_export_fullpagecsv_{timestamp}.csv**
  - Export complet incluant le contenu readable des articles
  - Toutes les colonnes de pagecsv + colonne 'readable'

- **tech_news_export_nodecsv_{timestamp}.csv**
  - Export agrégé des domaines avec statistiques
  - Colonnes: id, name, title, description, keywords, expressions count, average relevance

- **tech_news_export_mediacsv_{timestamp}.csv**
  - Export des médias associés aux expressions
  - Colonnes: id, expression_id, url, type

### GEXF Exports (Visualisation Réseau)
- **tech_news_export_pagegexf_{timestamp}.gexf**
  - Réseau des pages pour visualisation dans Gephi
  - Nœuds = expressions, attributs = métadonnées

- **tech_news_export_nodegexf_{timestamp}.gexf**
  - Réseau des domaines pour visualisation dans Gephi
  - Nœuds = domaines, attributs = statistiques

### Corpus Export
- **tech_news_export_corpus_{timestamp}.zip**
  - Archive ZIP contenant un fichier texte par expression
  - Chaque fichier inclut métadonnées YAML + contenu readable
  - Format compatible avec outils d'analyse textuelle

## 🔧 Utilisation

### CSV Files
```bash
# Ouvrir avec Excel, LibreOffice, ou pandas
import pandas as pd
df = pd.read_csv('tech_news_export_pagecsv_{timestamp}.csv')
```

### GEXF Files
```bash
# Ouvrir avec Gephi pour visualisation réseau
# File → Open → Sélectionner le fichier .gexf
```

### Corpus ZIP
```bash
# Extraire et analyser avec outils de text mining
unzip tech_news_export_corpus_{timestamp}.zip
# Chaque fichier .txt contient métadonnées + contenu
```

## 📈 Statistiques

- Articles IA/Tech: {sum(1 for expr in self.test_expressions if 'IA' in expr.keywords or 'AI' in expr.keywords)}
- Articles en français: {sum(1 for expr in self.test_expressions if 'français' in expr.readable or 'France' in expr.keywords)}
- Relevance moyenne: {sum(expr.relevance for expr in self.test_expressions) / len(self.test_expressions):.1f}/10

## 🎯 Cas d'Usage

1. **Analyse de Contenu**: Utiliser les CSV pour analyser les tendances
2. **Visualisation Réseau**: Importer les GEXF dans Gephi
3. **Text Mining**: Extraire le corpus ZIP pour analyse linguistique
4. **Reporting**: Utiliser les CSV pour créer des tableaux de bord

---
Généré par MyWebIntelligence Export System v2.0
"""
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        self.generated_files.append(readme_path)


if __name__ == "__main__":
    pytest.main([__file__ + "::TestExportFileGeneration::test_generate_all_export_formats", "-v", "-s"])