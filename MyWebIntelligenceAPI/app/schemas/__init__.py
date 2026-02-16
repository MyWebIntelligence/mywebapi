"""
Schémas Pydantic pour l'API MyWebIntelligence

Ces schémas sont utilisés pour la validation des données entrantes et sortantes
de l'API, assurant la cohérence et la sécurité des échanges.
"""

from .user import (
    User, UserCreate, UserUpdate, Token, TokenData,
    UserRegister, UserAdminResponse, UserListResponse,
    BlockUserRequest, SetRoleRequest, AdminStatsResponse,
    ForgotPasswordRequest, ResetPasswordRequest, AdminUserUpdate,
)
from .land import Land, LandCreate, LandUpdate, LandAddTerms, LandAddUrls
from .domain import Domain, DomainCreate, DomainUpdate
from .expression import Expression, ExpressionCreate, ExpressionUpdate
from .tag import Tag, TagCreate, TagUpdate
from .tagged_content import TaggedContent, TaggedContentCreate, TaggedContentUpdate
from .media import Media, MediaCreate, MediaUpdate
from .job import CrawlJobBase, CrawlJobCreate, CrawlJobResponse, CrawlRequest
from .export import Export, ExportCreate, ExportUpdate
