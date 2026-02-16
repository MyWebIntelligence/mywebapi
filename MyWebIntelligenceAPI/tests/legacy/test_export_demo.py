"""
Test de démonstration de génération de fichiers d'export
Génère des fichiers d'export avec des données simulées
"""

import pytest
import os
import tempfile
from datetime import datetime
from zipfile import ZipFile
from lxml import etree
from unittest.mock import MagicMock

from app.services.export_service_sync import SyncExportService


class TestExportDemo:
    """Test de démonstration des exports avec données simulées"""
    
    def setup_method(self):
        """Setup avec mock de base de données"""
        self.mock_db = MagicMock()
        self.export_service = SyncExportService(self.mock_db)
        self.generated_files = []
        
        # Données simulées réalistes
        self.mock_data_pagecsv = [
            {
                'id': 1,
                'url': 'https://techcrunch.com/2025/07/04/ai-breakthrough-new-language-model',
                'title': 'AI Breakthrough: Revolutionary New Language Model Achieves Human-Level Understanding',
                'description': 'Researchers announce a major breakthrough in artificial intelligence with a new language model.',
                'keywords': 'AI,artificial intelligence,language model,breakthrough,technology',
                'relevance': 9,
                'depth': 1,
                'domain_id': 1,
                'domain_name': 'techcrunch.com',
                'domain_description': 'Site d\'actualités technologiques',
                'domain_keywords': 'tech,startup,innovation'
            },
            {
                'id': 2,
                'url': 'https://lemonde.fr/technologies/2025/07/04/france-investit-ia-recherche',
                'title': 'La France investit massivement dans la recherche en intelligence artificielle',
                'description': 'Le gouvernement français annonce un plan d\'investissement de 2 milliards d\'euros pour développer la recherche en IA.',
                'keywords': 'France,investissement,IA,recherche,gouvernement,technologie',
                'relevance': 8,
                'depth': 1,
                'domain_id': 2,
                'domain_name': 'lemonde.fr',
                'domain_description': 'Journal français d\'information',
                'domain_keywords': 'actualités,france,monde'
            },
            {
                'id': 3,
                'url': 'https://github.com/blog/2025-07-04-copilot-updates',
                'title': 'GitHub Copilot: Major Updates Enhance Developer Productivity',
                'description': 'GitHub announces significant improvements to Copilot, including better code suggestions.',
                'keywords': 'GitHub,Copilot,AI,programming,development,productivity',
                'relevance': 7,
                'depth': 2,
                'domain_id': 3,
                'domain_name': 'github.com',
                'domain_description': 'Plateforme de développement collaboratif',
                'domain_keywords': 'code,git,développement'
            }
        ]
        
        self.mock_data_fullpagecsv = [
            {**item, 'readable': f'Contenu lisible complet de l\'article {item["id"]}. ' + 
             'Cette technologie révolutionnaire promet de transformer de nombreux secteurs industriels. ' * 10}
            for item in self.mock_data_pagecsv
        ]
        
        self.mock_data_nodecsv = [
            {
                'id': 1,
                'name': 'techcrunch.com',
                'title': 'TechCrunch',
                'description': 'Site d\'actualités technologiques',
                'keywords': 'tech,startup,innovation',
                'expressions': 1,
                'average_relevance': 9.0
            },
            {
                'id': 2,
                'name': 'lemonde.fr',
                'title': 'Le Monde',
                'description': 'Journal français d\'information',
                'keywords': 'actualités,france,monde',
                'expressions': 1,
                'average_relevance': 8.0
            },
            {
                'id': 3,
                'name': 'github.com',
                'title': 'GitHub',
                'description': 'Plateforme de développement collaboratif',
                'keywords': 'code,git,développement',
                'expressions': 1,
                'average_relevance': 7.0
            }
        ]
        
        self.mock_data_corpus = [
            {
                'id': item['id'],
                'url': item['url'],
                'title': item['title'],
                'description': item['description'],
                'readable': f'Contenu complet de l\'article {item["id"]}. ' + item['description'] + ' ' +
                           'Ce contenu détaillé permettrait une analyse approfondie du sujet traité. ' * 20,
                'domain': item['domain_name']
            }
            for item in self.mock_data_pagecsv
        ]
    
    def teardown_method(self):
        """Affichage des fichiers générés"""
        if self.generated_files:
            print(f"\n📁 FICHIERS D'EXPORT GÉNÉRÉS:")
            total_size = 0
            for file_path in self.generated_files:
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    print(f"  📄 {file_path}")
                    print(f"      Taille: {file_size} bytes ({file_size/1024:.1f} KB)")
            
            print(f"\n📊 Total: {len(self.generated_files)} fichiers, {total_size} bytes ({total_size/1024:.1f} KB)")
            print(f"\n✅ Tous les fichiers sont disponibles et peuvent être consultés!")
    
    def test_generate_pagecsv_demo(self):
        """Génère un fichier CSV basique de démonstration"""
        # Mock de la méthode get_sql_data
        self.export_service.get_sql_data = MagicMock(return_value=self.mock_data_pagecsv)
        
        # Créer le fichier d'export
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/demo_export_pagecsv_{timestamp}.csv"
        
        count = self.export_service.write_pagecsv(filename, land_id=1, minimum_relevance=1)
        
        # Vérifications
        assert os.path.exists(filename)
        assert count == 3
        
        # Vérifier le contenu CSV
        import csv
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
            assert len(rows) == 4  # Header + 3 data rows
            header = rows[0]
            assert 'title' in header
            assert 'url' in header
            assert 'relevance' in header
            
            # Vérifier une ligne de données
            first_row = rows[1]
            assert 'AI Breakthrough' in first_row[header.index('title')]
            assert 'techcrunch.com' in first_row[header.index('url')]
        
        self.generated_files.append(filename)
        print(f"✅ CSV basique généré: {filename}")
    
    def test_generate_fullpagecsv_demo(self):
        """Génère un fichier CSV complet avec contenu readable"""
        self.export_service.get_sql_data = MagicMock(return_value=self.mock_data_fullpagecsv)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/demo_export_fullpagecsv_{timestamp}.csv"
        
        count = self.export_service.write_fullpagecsv(filename, land_id=1, minimum_relevance=1)
        
        assert os.path.exists(filename)
        assert count == 3
        
        # Vérifier que le contenu readable est inclus
        import csv
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            header = rows[0]
            assert 'readable' in header
            
            # Vérifier qu'il y a du contenu readable
            readable_index = header.index('readable')
            for row in rows[1:]:
                assert len(row[readable_index]) > 100  # Contenu substantiel
        
        self.generated_files.append(filename)
        print(f"✅ CSV complet généré: {filename}")
    
    def test_generate_nodecsv_demo(self):
        """Génère un fichier CSV des domaines avec statistiques"""
        self.export_service.get_sql_data = MagicMock(return_value=self.mock_data_nodecsv)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/demo_export_nodecsv_{timestamp}.csv"
        
        count = self.export_service.write_nodecsv(filename, land_id=1, minimum_relevance=1)
        
        assert os.path.exists(filename)
        assert count == 3
        
        # Vérifier les statistiques de domaines
        import csv
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            header = rows[0]
            assert 'expressions' in header
            assert 'average_relevance' in header
        
        self.generated_files.append(filename)
        print(f"✅ CSV domaines généré: {filename}")
    
    def test_generate_corpus_demo(self):
        """Génère un corpus ZIP avec fichiers texte individuels"""
        self.export_service.get_sql_data = MagicMock(return_value=self.mock_data_corpus)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/demo_export_corpus_{timestamp}.zip"
        
        count = self.export_service.write_corpus(filename, land_id=1, minimum_relevance=1)
        
        assert os.path.exists(filename)
        assert count == 3
        
        # Vérifier le contenu du ZIP
        with ZipFile(filename, 'r') as archive:
            files = archive.namelist()
            assert len(files) == 3
            
            # Vérifier le contenu d'un fichier
            first_file_content = archive.read(files[0]).decode('utf-8')
            assert first_file_content.startswith('---')
            assert 'Title:' in first_file_content
            assert 'Source:' in first_file_content
            assert 'Contenu complet' in first_file_content
        
        self.generated_files.append(filename)
        print(f"✅ Corpus ZIP généré: {filename}")
    
    def test_generate_pagegexf_demo(self):
        """Génère un fichier GEXF pour visualisation réseau des pages"""
        self.export_service.get_sql_data = MagicMock(return_value=self.mock_data_pagecsv)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/demo_export_pagegexf_{timestamp}.gexf"
        
        count = self.export_service.write_pagegexf(filename, land_id=1, minimum_relevance=1)
        
        assert os.path.exists(filename)
        assert count == 3
        
        # Vérifier la structure GEXF
        tree = etree.parse(filename)
        root = tree.getroot()
        assert root.tag == 'gexf'
        assert root.get('version') == '1.2'
        
        # Vérifier les métadonnées
        meta = root.find('meta')
        assert meta is not None
        assert meta.get('creator') == 'MyWebIntelligence'
        
        # Vérifier les nœuds
        graph = root.find('graph')
        nodes = graph.find('nodes')
        node_elements = nodes.findall('node')
        assert len(node_elements) == 3
        
        self.generated_files.append(filename)
        print(f"✅ GEXF pages généré: {filename}")
    
    def test_generate_nodegexf_demo(self):
        """Génère un fichier GEXF pour visualisation réseau des domaines"""
        self.export_service.get_sql_data = MagicMock(return_value=self.mock_data_nodecsv)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/demo_export_nodegexf_{timestamp}.gexf"
        
        count = self.export_service.write_nodegexf(filename, land_id=1, minimum_relevance=1)
        
        assert os.path.exists(filename)
        assert count == 3
        
        # Vérifier la structure GEXF
        tree = etree.parse(filename)
        root = tree.getroot()
        assert root.tag == 'gexf'
        
        self.generated_files.append(filename)
        print(f"✅ GEXF domaines généré: {filename}")
    
    def test_generate_all_formats_demo(self):
        """Test complet: génère tous les formats d'export"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"\n🎯 Génération complète de tous les formats d'export")
        print(f"📅 Timestamp: {timestamp}")
        print(f"📊 Données: 3 articles tech simulés (TechCrunch, Le Monde, GitHub)")
        
        # Configurer les mocks
        formats_config = {
            'pagecsv': (self.mock_data_pagecsv, self.export_service.write_pagecsv),
            'fullpagecsv': (self.mock_data_fullpagecsv, self.export_service.write_fullpagecsv),
            'nodecsv': (self.mock_data_nodecsv, self.export_service.write_nodecsv),
            'corpus': (self.mock_data_corpus, self.export_service.write_corpus),
            'pagegexf': (self.mock_data_pagecsv, self.export_service.write_pagegexf),
            'nodegexf': (self.mock_data_nodecsv, self.export_service.write_nodegexf)
        }
        
        for format_name, (mock_data, write_method) in formats_config.items():
            self.export_service.get_sql_data = MagicMock(return_value=mock_data)
            
            filename = f"/tmp/complete_demo_{format_name}_{timestamp}"
            if format_name.endswith('csv'):
                filename += '.csv'
            elif format_name.endswith('gexf'):
                filename += '.gexf'
            elif format_name == 'corpus':
                filename += '.zip'
            
            count = write_method(filename, land_id=1, minimum_relevance=1)
            
            assert os.path.exists(filename)
            assert count == len(mock_data)
            
            self.generated_files.append(filename)
            file_size = os.path.getsize(filename)
            print(f"  ✅ {format_name.upper()}: {count} records → {os.path.basename(filename)} ({file_size} bytes)")
        
        # Créer un fichier README
        readme_path = f"/tmp/README_exports_{timestamp}.md"
        self._create_demo_readme(readme_path, timestamp)
        self.generated_files.append(readme_path)
        
        print(f"\n📋 {len(self.generated_files)} fichiers générés au total")
        print(f"📖 README créé: {readme_path}")
    
    def _create_demo_readme(self, readme_path, timestamp):
        """Crée un fichier README pour la démonstration"""
        readme_content = f"""# MyWebIntelligence - Démonstration Export

**Date de génération**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Timestamp**: {timestamp}

## 📊 Données de Démonstration

3 articles simulés sur l'actualité technologique :

1. **TechCrunch** - "AI Breakthrough: Revolutionary New Language Model" (Relevance: 9/10)
2. **Le Monde** - "La France investit massivement dans la recherche en IA" (Relevance: 8/10)  
3. **GitHub** - "GitHub Copilot: Major Updates Enhance Developer Productivity" (Relevance: 7/10)

## 📁 Fichiers Générés

### CSV Exports
- `complete_demo_pagecsv_{timestamp}.csv` - Export basique des pages
- `complete_demo_fullpagecsv_{timestamp}.csv` - Export complet avec contenu
- `complete_demo_nodecsv_{timestamp}.csv` - Statistiques des domaines

### Visualisation Réseau (GEXF)
- `complete_demo_pagegexf_{timestamp}.gexf` - Réseau des pages (pour Gephi)
- `complete_demo_nodegexf_{timestamp}.gexf` - Réseau des domaines (pour Gephi)

### Corpus Textuel
- `complete_demo_corpus_{timestamp}.zip` - Archive avec fichiers texte individuels

## 🔧 Comment Utiliser

1. **CSV**: Ouvrir avec Excel, Google Sheets, ou pandas Python
2. **GEXF**: Importer dans Gephi pour visualisation réseau
3. **Corpus**: Extraire le ZIP et analyser les fichiers .txt

## ✅ Validation

Tous les fichiers ont été générés et validés avec succès !
Chaque format contient les 3 articles de test avec leurs métadonnées complètes.

---
Généré par MyWebIntelligence Export System - Test de Démonstration
"""
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])