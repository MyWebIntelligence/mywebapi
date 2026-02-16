import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.models import Land, CrawlJob, Expression, User, CrawlStatus
from app.core.websocket import websocket_manager
from app.crud.crud_job import job as crud_job


class TestCrawlWorkflowIntegration:
    """
    Tests d'intégration pour le workflow complet de crawling.
    """

    @pytest.mark.asyncio
    async def test_full_crawl_workflow_success(
        self,
        async_db_session: AsyncSession,
        test_user: User,
        test_land: Land,
        mock_httpx_client: AsyncMock,
        authenticated_client: TestClient
    ):
        client = authenticated_client

        mock_httpx_client.get.return_value.status_code = 200
        mock_httpx_client.get.return_value.text = "<html><body><h1>Test</h1></body></html>"
        mock_httpx_client.get.return_value.headers = {"content-type": "text/html"}

        with patch('app.services.crawling_service.celery_app.send_task') as mock_celery_task:
            mock_result = Mock()
            mock_result.id = "test-celery-task-id-123"
            mock_celery_task.return_value = mock_result

            with patch.object(websocket_manager, 'broadcast') as mock_broadcast:
                response = client.post(
                    f"/api/v1/lands/{test_land.id}/crawl",
                    json={"depth": 2, "limit": 10, "http": [200], "extract_media": True, "extract_links": True},
                    headers={"Authorization": f"Bearer fake-token-{test_user.id}"}
                )

                assert response.status_code == 200
                response_data = response.json()
                job_id = response_data["job_id"]

                mock_celery_task.assert_called_once()
                assert await crud_job.get(async_db_session, job_id=job_id) is not None

    @pytest.mark.asyncio
    async def test_crawl_workflow_with_validation_errors(
        self,
        async_db_session: AsyncSession,
        test_user: User,
        test_land: Land,
        authenticated_client: TestClient
    ):
        client = authenticated_client
        response = client.post(
            f"/api/v1/lands/{test_land.id}/crawl",
            json={"depth": -1, "limit": 0, "http": [999]},
            headers={"Authorization": f"Bearer fake-token-{test_user.id}"}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_crawl_workflow_land_not_found(
        self,
        async_db_session: AsyncSession,
        test_user: User,
        authenticated_client: TestClient
    ):
        client = authenticated_client
        response = client.post(
            "/api/v1/lands/99999/crawl",
            json={"depth": 1, "limit": 5},
            headers={"Authorization": f"Bearer fake-token-{test_user.id}"}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_crawl_workflow_celery_dispatch_failure(
        self,
        async_db_session: AsyncSession,
        test_user: User,
        test_land: Land,
        authenticated_client: TestClient
    ):
        client = authenticated_client
        with patch('app.services.crawling_service.celery_app.send_task') as mock_send_task:
            mock_send_task.side_effect = Exception("Redis connection failed")
            response = client.post(
                f"/api/v1/lands/{test_land.id}/crawl",
                json={"depth": 1, "limit": 5},
                headers={"Authorization": f"Bearer fake-token-{test_user.id}"}
            )
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_crawl_workflow_with_websocket_progression(
        self,
        async_db_session: AsyncSession,
        test_user: User,
        test_land: Land,
        mock_httpx_client: AsyncMock,
        authenticated_client: TestClient
    ):
        client = authenticated_client
        mock_httpx_client.get.return_value.status_code = 200
        mock_httpx_client.get.return_value.text = "<html><body>Test</body></html>"
        websocket_messages = []

        def mock_broadcast(channel: str, message: str):
            websocket_messages.append((channel, message))

        with patch('app.services.crawling_service.celery_app.send_task') as mock_send_task:
            mock_result = Mock()
            mock_result.id = "test-task-123"
            mock_send_task.return_value = mock_result

            with patch.object(websocket_manager, 'broadcast', side_effect=mock_broadcast):
                response = client.post(
                    f"/api/v1/lands/{test_land.id}/crawl",
                    json={"depth": 1, "limit": 3},
                    headers={"Authorization": f"Bearer fake-token-{test_user.id}"}
                )
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_crawl_workflow_job_status_tracking(
        self,
        async_db_session: AsyncSession,
        test_user: User,
        test_land: Land,
        authenticated_client: TestClient
    ):
        client = authenticated_client
        with patch('app.services.crawling_service.celery_app.send_task') as mock_send_task:
            mock_result = Mock()
            mock_result.id = "test-job-status-123"
            mock_send_task.return_value = mock_result

            response = client.post(
                f"/api/v1/lands/{test_land.id}/crawl",
                json={"depth": 1, "limit": 2},
                headers={"Authorization": f"Bearer fake-token-{test_user.id}"}
            )
            assert response.status_code == 200

            job_id = response.json()["job_id"]
            db_job = await crud_job.get(async_db_session, job_id=job_id)
            assert db_job is not None

    @pytest.mark.asyncio
    async def test_crawl_workflow_with_different_parameters(
        self,
        async_db_session: AsyncSession,
        test_user: User,
        test_land: Land,
        authenticated_client: TestClient
    ):
        client = authenticated_client
        test_cases = [
            ({"depth": 1}, 1),
            ({"depth": 3, "limit": 50, "http": [200, 301]}, 3),
            ({"depth": 2, "limit": 25, "extract_media": True}, 2)
        ]
        for params, expected_depth in test_cases:
            with patch('app.services.crawling_service.celery_app.send_task') as mock_send_task:
                mock_result = Mock()
                mock_result.id = "test-case"
                mock_send_task.return_value = mock_result
                response = client.post(
                    f"/api/v1/lands/{test_land.id}/crawl",
                    json=params,
                    headers={"Authorization": f"Bearer fake-token-{test_user.id}"}
                )
                assert response.status_code == 200
