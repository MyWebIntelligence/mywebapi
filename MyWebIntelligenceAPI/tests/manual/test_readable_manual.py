#!/usr/bin/env python3
"""
Script de test manuel pour le pipeline readable.
Permet de tester rapidement sans setup complet.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.schemas.readable import MergeStrategy, ExtractionResult, MediaInfo, LinkInfo


class MockDB:
    """Mock simple de base de données pour les tests."""
    def __init__(self):
        self.committed = False
        self.added_objects = []
    
    async def execute(self, query):
        return MockResult()
    
    async def commit(self):
        self.committed = True
    
    async def rollback(self):
        pass
    
    async def flush(self):
        pass
    
    def add(self, obj):
        self.added_objects.append(obj)
    
    async def get(self, model, id):
        return MockLand() if model.__name__ == 'Land' else None


class MockResult:
    """Mock de résultat de requête."""
    def __init__(self):
        pass
    
    def first(self):
        return MockRow()
    
    def scalar(self):
        return 25
    
    def scalars(self):
        return MockScalars()


class MockScalars:
    """Mock de scalars result."""
    def all(self):
        return [MockExpression()]


class MockRow:
    """Mock de ligne de résultat."""
    def __init__(self):
        self.total = 100
        self.with_readable = 75
        self.last_processed = datetime.now()


class MockExpression:
    """Mock d'expression pour les tests."""
    def __init__(self):
        self.id = 1
        self.url = "https://example.com/test"
        self.title = "Test Title"
        self.description = "Test description"
        self.readable = None
        self.lang = "fr"
        self.land_id = 1
        self.published_at = None
        self.readable_at = None
        self.relevance = None
        self.fetched_at = datetime.now()


class MockLand:
    """Mock de land pour les tests."""
    def __init__(self):
        self.id = 1
        self.name = "Test Land"
        self.description = "Test land description"
        self.words = [{"word": "test"}, {"word": "example"}]


async def test_readable_service_basic():
    """Test basique du ReadableService."""
    print("🧪 Test ReadableService Basic...")
    
    try:
        from app.services.readable_service import ReadableService
        
        # Initialiser avec mock DB
        mock_db = MockDB()
        service = ReadableService(mock_db)
        
        # Test get_readable_stats
        stats = await service.get_readable_stats(land_id=1)
        print(f"✅ Stats récupérées: {stats.total_expressions} expressions")
        
        # Test get_expressions_to_process
        expressions = await service.get_expressions_to_process(land_id=1, limit=10)
        print(f"✅ Expressions à traiter: {len(expressions)}")
        
        print("✅ ReadableService basic tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ ReadableService test failed: {e}")
        return False


def test_merge_strategies():
    """Test des stratégies de fusion."""
    print("\n🧪 Test Merge Strategies...")
    
    try:
        from app.services.readable_service import ReadableService
        
        mock_db = MockDB()
        service = ReadableService(mock_db)
        
        # Mock expression
        expression = MockExpression()
        expression.title = "Old Title"
        expression.readable = "Old content"
        
        # Mock extraction result
        extraction = ExtractionResult(
            url="https://example.com/test",
            title="New Longer Test Title",
            description="New longer description",
            readable="# New Content\n\nNew readable content.",
            language="en",
            published_at=datetime(2023, 1, 1),
            author="Test Author",
            media_urls=[],
            link_urls=[],
            extraction_source="trafilatura",
            success=True
        )
        
        # Test SMART_MERGE
        expression_copy = MockExpression()
        expression_copy.title = "Old Title"
        expression_copy.readable = "Old content"
        
        updated = service._apply_merge_strategy(
            expression_copy, extraction, MergeStrategy.SMART_MERGE
        )
        
        assert updated is True
        assert expression_copy.title == "New Longer Test Title"  # Plus long
        assert expression_copy.readable == "# New Content\n\nNew readable content."  # Nouveau
        print("✅ SMART_MERGE strategy works")
        
        # Test MERCURY_PRIORITY
        expression_copy2 = MockExpression()
        expression_copy2.title = "Old Title"
        expression_copy2.readable = "Old content"
        
        updated2 = service._apply_merge_strategy(
            expression_copy2, extraction, MergeStrategy.MERCURY_PRIORITY
        )
        
        assert updated2 is True
        assert expression_copy2.title == "New Longer Test Title"  # Écrasé
        print("✅ MERCURY_PRIORITY strategy works")
        
        # Test PRESERVE_EXISTING
        expression_copy3 = MockExpression()
        expression_copy3.title = "Existing Title"
        expression_copy3.readable = "Existing content"
        
        updated3 = service._apply_merge_strategy(
            expression_copy3, extraction, MergeStrategy.PRESERVE_EXISTING
        )
        
        assert updated3 is False  # Rien changé
        assert expression_copy3.title == "Existing Title"  # Préservé
        print("✅ PRESERVE_EXISTING strategy works")
        
        print("✅ All merge strategies tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Merge strategies test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_media_link_extractor():
    """Test du MediaLinkExtractor."""
    print("\n🧪 Test MediaLinkExtractor...")
    
    try:
        from app.services.media_link_extractor import MediaLinkExtractor
        
        mock_db = MockDB()
        extractor = MediaLinkExtractor(mock_db)
        
        # Test markdown content
        markdown = """
# Test Article

![Alt text](https://example.com/image.jpg "Image title")
![](https://example.com/image2.png)
<img src="https://example.com/html-image.gif" alt="HTML alt">

[Internal link](https://example.com/page "Link title")
[External link](https://external.org/page)
<a href="https://example.com/html-link">HTML link</a>
        """
        
        base_url = "https://example.com/"
        
        # Test extraction médias
        media_list = extractor.extract_media_from_markdown(markdown, base_url)
        print(f"✅ Médias extraits: {len(media_list)}")
        
        assert len(media_list) == 3
        assert media_list[0].url == "https://example.com/image.jpg"
        assert media_list[0].alt_text == "Alt text"
        assert media_list[0].title == "Image title"
        
        # Test extraction liens
        link_list = extractor.extract_links_from_markdown(markdown, base_url)
        print(f"✅ Liens extraits: {len(link_list)}")
        
        assert len(link_list) == 3
        assert link_list[0].url == "https://example.com/page"
        assert link_list[0].link_type == "internal"
        assert link_list[1].link_type == "external"
        
        print("✅ MediaLinkExtractor tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ MediaLinkExtractor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_validation_service():
    """Test du LLMValidationService."""
    print("\n🧪 Test LLMValidationService...")
    
    try:
        from app.services.llm_validation_service import LLMValidationService
        
        mock_db = MockDB()
        service = LLMValidationService(mock_db)
        
        # Test build prompt
        expression = MockExpression()
        land = MockLand()
        
        prompt = service._build_relevance_prompt(expression, land)
        print(f"✅ Prompt généré: {len(prompt)} caractères")
        
        assert "Test Land" in prompt
        assert "Test Title" in prompt
        assert "oui" in prompt
        assert "non" in prompt
        
        # Test parse responses
        assert service._parse_yes_no_response("oui") is True
        assert service._parse_yes_no_response("non") is False
        assert service._parse_yes_no_response("unclear") is False
        print("✅ Response parsing works")
        
        # Test URL cleaning
        test_url = "https://example.com/image.jpg?utm_source=google&ref=tracking"
        # Cette méthode est dans MediaLinkExtractor, pas LLMValidationService
        
        print("✅ LLMValidationService tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ LLMValidationService test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_schemas():
    """Test des schemas Pydantic."""
    print("\n🧪 Test Schemas...")
    
    try:
        from app.schemas.readable import (
            MergeStrategy, ReadableRequest, ReadableProcessingResult,
            ExtractionResult, MediaInfo, LinkInfo
        )
        
        # Test MergeStrategy enum
        assert MergeStrategy.SMART_MERGE == "smart_merge"
        assert MergeStrategy.MERCURY_PRIORITY == "mercury_priority"
        print("✅ MergeStrategy enum works")
        
        # Test ReadableRequest
        request = ReadableRequest(
            limit=10,
            depth=2,
            merge_strategy=MergeStrategy.SMART_MERGE,
            enable_llm=True
        )
        assert request.limit == 10
        assert request.merge_strategy == MergeStrategy.SMART_MERGE
        print("✅ ReadableRequest works")
        
        # Test ExtractionResult
        result = ExtractionResult(
            url="https://example.com/test",
            title="Test Title",
            readable="# Test",
            media_urls=["https://example.com/image.jpg"],
            link_urls=["https://example.com/link"],
            extraction_source="trafilatura",
            success=True
        )
        assert result.success is True
        assert len(result.media_urls) == 1
        print("✅ ExtractionResult works")
        
        print("✅ All schemas tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Schemas test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Lancer tous les tests manuels."""
    print("🚀 Lancement des tests manuels du pipeline readable\n")
    
    results = []
    
    # Tests synchrones
    results.append(test_merge_strategies())
    results.append(test_media_link_extractor())
    results.append(test_llm_validation_service())
    results.append(test_schemas())
    
    # Tests asynchrones
    results.append(await test_readable_service_basic())
    
    # Résumé
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 Résultats des tests: {passed}/{total} réussis")
    
    if passed == total:
        print("🎉 Tous les tests sont passés avec succès!")
        print("\n✅ Le pipeline readable est prêt à être utilisé!")
    else:
        print(f"❌ {total - passed} tests ont échoué")
        print("🔧 Vérifiez les erreurs ci-dessus")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
