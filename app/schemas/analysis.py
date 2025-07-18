from pydantic import HttpUrl, field_validator, Field
from typing import List, Optional, Any, Tuple, Union
from datetime import datetime
from app.core.constants import AnalysisStatus as AnalysisStatusConstants
from app.core.models import CamelCaseModel, to_camel_case

class AnalyzeRequest(CamelCaseModel):
    url: HttpUrl

# AI Presence Analysis Models
class AIPresenceModelResults(CamelCaseModel):
    industry: bool
    name: bool
    product: bool
    uncertainty: bool
    score: float

class AIPresenceResult(CamelCaseModel):
    openai: Optional[AIPresenceModelResults] = None
    anthropic: Optional[AIPresenceModelResults] = None
    gemini: Optional[AIPresenceModelResults] = None
    perplexity: Optional[AIPresenceModelResults] = None
    score: float


# Competitor Landscape Analysis Models
class LLMCompetitorResult(CamelCaseModel):
    competitors: List[str]
    included: bool
    score: float

class CompetitorLandscapeResult(CamelCaseModel):
    openai: Optional[LLMCompetitorResult] = None
    anthropic: Optional[LLMCompetitorResult] = None
    gemini: Optional[LLMCompetitorResult] = None
    perplexity: Optional[LLMCompetitorResult] = None


# Strategy Review Analysis Models
class AnswerabilityResult(CamelCaseModel):
    total_phrases: int
    is_good_length_phrase: int
    is_conversational_phrase: int
    has_statistics_phrase: int
    has_citation_phrase: int
    has_citations_section: bool
    score: float

class WikipediaResult(CamelCaseModel):
    has_wikipedia_page: bool
    wikipedia_url: Optional[str] = None
    score: float

class RedditMetricResult(CamelCaseModel):
    label: str
    raw_value: Any
    score: float

class RedditResult(CamelCaseModel):
    subreddit: RedditMetricResult
    members: RedditMetricResult
    mention_volume: RedditMetricResult
    engagement: RedditMetricResult
    recency: RedditMetricResult
    diversity: RedditMetricResult
    total_score: float = Field(..., ge=0, le=100) 

class WebPresenceResult(CamelCaseModel):
    wikipedia: WikipediaResult
    reddit: RedditResult
    total_score: float

class StructuredDataSemanticElements(CamelCaseModel):
    present: bool
    unique_types_found: List[str]
    count_unique_types: int
    all_tags_count: int
    semantic_tags_count: int
    non_semantic_tags_count: int
    semantic_ratio: float

class StructuredDataSpecificSchemas(CamelCaseModel):
    faq_page: bool
    article: bool
    review: bool

class StructuredDataResult(CamelCaseModel):
    schema_markup_present: bool
    schema_types_found: List[str]
    specific_schemas: StructuredDataSpecificSchemas
    semantic_elements: StructuredDataSemanticElements
    score: float

class PreRenderedContent(CamelCaseModel):
    likely_pre_rendered: bool
    text_length: int
    js_framework_hint: bool

class LanguageDetection(CamelCaseModel):
    detected_languages: Optional[List[str]] = None
    is_english: Optional[bool] = None
    english_version_url: Optional[str] = None

class AiCrawlerAccessibilityResult(CamelCaseModel):
    sitemap_found: bool
    robots_txt_found: bool
    llms_txt_found: bool
    llm_txt_found: bool
    pre_rendered_content: PreRenderedContent
    language: LanguageDetection
    score: float

class StrategyReviewResult(CamelCaseModel):
    answerability: AnswerabilityResult
    web_presence: WebPresenceResult
    structured_data: StructuredDataResult
    ai_crawler_accessibility: AiCrawlerAccessibilityResult


# Base Analysis Item
class BaseAnalysisItem(CamelCaseModel):
    title: str
    score: Optional[float] = None
    completed: bool

class AIPresenceAnalysisItem(BaseAnalysisItem):
    id: str = "aiPresence"
    result: AIPresenceResult

class CompetitorLandscapeAnalysisItem(BaseAnalysisItem):
    id: str = "competitorLandscape"
    result: CompetitorLandscapeResult

class StrategyReviewAnalysisItem(BaseAnalysisItem):
    id: str = "strategyReview"
    result: StrategyReviewResult

# Union type for analysis items
AnalysisItemData = Union[AIPresenceAnalysisItem, CompetitorLandscapeAnalysisItem, StrategyReviewAnalysisItem]


class AnalysisTask(CamelCaseModel):
    id: str
    title: str
    result: Any
    score: float
    completed: bool

    @field_validator('id', mode='before')
    def camel_case_id_value(cls, v: Any) -> Any:
        if isinstance(v, str):
            return to_camel_case(v)
        return v

class SharingMetadata(CamelCaseModel):
    is_public: bool
    share_token: Optional[str] = None
    shared_at: Optional[datetime] = None
    view_count: int = 0
    share_url: Optional[str] = None

class CompanyInfo(CamelCaseModel):
    name: str
    industry: str
    key_products_services: List[str]
    description: str

class AnalysisResult(CamelCaseModel):
    url: HttpUrl
    score: float
    title: str
    dummy: bool
    analysis_synthesis: str
    deleted: Optional[bool] = False
    analysis_items: List[AnalysisItemData]
    created_at: datetime
    sharing: Optional[SharingMetadata] = None  # Only present for owners
    company_info: Optional[CompanyInfo] = None

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "score": 85.5,
                "title": "Analysis Title",
                "dummy": False,
                "analysis_synthesis": "This is an example of the analysis synthesis",
                "deleted": False,
                "company_info": {
                    "name": "Company Name",
                    "industry": "Technology",
                    "key_products_services": ["Web Development", "Software Solutions"],
                    "description": "A technology company providing web development services"
                },
                "analysis_items": [
                    {
                        "id": "aiPresence",
                        "title": "AI Presence Analysis",
                        "score": 75.0,
                        "completed": True,
                        "result": {
                            "openai": {
                                "industry": True,
                                "name": True,
                                "product": False,
                                "uncertainty": False,
                                "score": 80.0
                            },
                            "score": 75.0
                        }
                    },
                    {
                        "id": "competitorLandscape",
                        "title": "Competitor Landscape Analysis", 
                        "score": 90.0,
                        "completed": True,
                        "result": {
                            "openai": {
                                "competitors": ["Company A", "Company B"],
                                "included": True,
                                "score": 90.0
                            }
                        }
                    },
                    {
                        "id": "strategyReview",
                        "title": "Strategy Review Analysis",
                        "score": 88.0,
                        "completed": True,
                        "result": {
                            "answerability": {
                                "total_phrases": 100,
                                "is_good_length_phrase": 50,
                                "is_conversational_phrase": 30,
                                "has_statistics_phrase": 20,
                                "has_citation_phrase": 15,
                                "has_citations_section": True,
                                "score": 85.0
                            },
                            "web_presence": {
                                "wikipedia": {
                                    "has_wikipedia_page": True,
                                    "wikipedia_url": "https://en.wikipedia.org/wiki/Example",
                                    "score": 50.0
                                },
                                "reddit": {
                                    "subreddit": {"label": "Subreddit ownership", "raw_value": True, "score": 7.5},
                                    "members": {"label": "Members", "raw_value": 1000, "score": 5.0},
                                    "mention_volume": {"label": "30-day mentions", "raw_value": 25, "score": 8.0},
                                    "engagement": {"label": "Avg karma+replies", "raw_value": 15.5, "score": 6.0},
                                    "recency": {"label": "Latest mention hrs", "raw_value": 12.5, "score": 7.0},
                                    "diversity": {"label": "Unique subreddits", "raw_value": 8, "score": 7.5},
                                    "total_score": 41.0
                                },
                                "total_score": 91.0
                            },
                            "structured_data": {
                                "schema_markup_present": True,
                                "schema_types_found": ["Organization", "Article"],
                                "specific_schemas": {
                                    "faq_page": False,
                                    "article": True,
                                    "review": False
                                },
                                "semantic_elements": {
                                    "present": True,
                                    "unique_types_found": ["header", "main", "article", "section"],
                                    "count_unique_types": 4,
                                    "all_tags_count": 150,
                                    "semantic_tags_count": 90,
                                    "non_semantic_tags_count": 60,
                                    "semantic_ratio": 0.6
                                },
                                "score": 75.0
                            },
                            "ai_crawler_accessibility": {
                                "sitemap_found": True,
                                "robots_txt_found": True,
                                "llms_txt_found": False,
                                "llm_txt_found": False,
                                "pre_rendered_content": {
                                    "likely_pre_rendered": True,
                                    "text_length": 2500,
                                    "js_framework_hint": False
                                },
                                "language": {
                                    "detected_languages": ["en"],
                                    "is_english": True,
                                    "english_version_url": None
                                },
                                "score": 85.0
                            }
                        }
                    }
                ],
                "created_at": "2023-07-10T14:23:56.123Z",
                "sharing": {
                    "isPublic": True,
                    "shareToken": "abc123def456ghi789",
                    "sharedAt": "2023-07-10T15:30:00.000Z",
                    "viewCount": 42,
                    "shareUrl": "results?share=abc123def456ghi789"
                }
            }
        }

class AnalysisStatus(CamelCaseModel):
    job_id: str
    status: AnalysisStatusConstants
    progress: Optional[float] = None
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "abc123",
                "status": AnalysisStatusConstants.PROCESSING,
                "progress": 0.75,
                "error": None
            }
        }

class ReportSummary(CamelCaseModel):
    url: HttpUrl
    title: str
    score: float
    created_at: datetime
    analysis_synthesis: str
    job_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "title": "Analysis Title",
                "score": 85.5,
                "createdAt": "2023-07-10T14:23:56.123Z",
                "analysisSynthesis": "Analysis Synthesis",
                "jobId": "abc123"
            }
        }

class ShareLink(CamelCaseModel):
    share_url: str

    class Config:
        json_schema_extra = {
            "example": {
                "shareUrl": "results?share=abc123def456ghi789"
            }
        } 