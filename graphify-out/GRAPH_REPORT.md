# Graph Report - flick-app  (2026-11-17)

## Corpus Check
- 249 files · ~376,054 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 59 file(s) not represented in the graph (top: .csv 48, (none) 7, .example 2)

## Summary
- 4261 nodes · 9227 edges · 211 communities (101 shown, 110 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1049 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8f9a289d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Batch3WorkerIntegrationTests
- Defense-in-Depth Debugging Strategies
- compute_recovery_lookup_digest
- django_db
- _make_movie
- router.tsx
- GuestConversionValidationAndRejectionTests
- WebSocketAuthenticationAndAuthorizationTests
- DiscoverPage.tsx
- apiRequest
- HardConstraintFilter
- TmdbChangesServiceTests
- LocalizedGenreRetrievalTests
- CinemaHeader
- run_staleness_sweep
- Batch5PersonalizationEvaluationTests
- DynamicMovieCatalogueTests
- IntelligenceWorkerProcess
- SessionPage.tsx
- compilerOptions
- CatalogueJob
- Stage3EndToEndProductValidationTests
- WebSocketRevocationTests
- ProposalExecutionWorker
- Pre1990ReleasePeriodFilterTests
- SessionLifecycleAndQuestionnaireRecoveryTests
- permissions.py
- transition_movie_classification
- acquire_tmdb_token
- Root Cause Tracing Techniques
- compilerOptions
- RoomRecommendationScenariosTestCase
- MatchConsumer
- Systematic Debugging
- manifest.json
- ProposalAPITestCase
- GuestProfile
- UserPreferenceData
- .get_recommendations
- StreamingFilterAuditTests
- backend/package.json
- Genre
- views.py
- UserProfile
- TestReliabilityAndRetrieval
- ScreeningSessionResultsAndStatsPersistenceTests
- DesignSystemGenerator
- core/urls.py
- .link_guest_to_user
- enrichment_handlers.py
- .agent/skills/ui-ux-pro-max/scripts/design_system.py
- TestCase
- DesignSystemGenerator
- Batch2EnrichmentAndWorkerTests
- scripts
- 6. Flick-Specific Error Handling Architecture
- 3. Complete HTTP Status Code Guide
- React + TypeScript + Vite
- vercel.json
- tmdb.py
- CatalogueQueueService
- evaluate_eligibility_predicates
- tmdb_rate_limiter.py
- sw.js
- TMDBTimeoutError
- test_proposals.py
- tsconfig.json
- Session
- GuestActivityTrackingTests
- django_db_models_deletion
- ConstraintExpansionProposal
- test_batch5_personalization.py
- .agent/skills/ui-ux-pro-max/scripts/core.py
- _assert_safe_local_database
- 9. Practical Troubleshooting Playbook
- ArchiveShelvesService
- SuperLikeReactionMatrixIntegrationTests
- ConstraintExhaustionNoticeModal.tsx
- ui-ux-pro-max
- .anonymize_and_delete_user
- api.ts
- UserIdentityLinkModelTests
- HardConstraints
- TmdbChangesCheckpoint
- .authenticate
- PostgreSQLQueueConcurrencyTests
- ui-ux-pro-max
- .agents/skills/ui-ux-pro-max/scripts/design_system.py
- ThemeContext.tsx
- UserIdentityLink
- set_redis_client
- .test_concurrent_host_and_guest_submissions_resolve_atomically
- Swipe
- .agent/skills/ui-ux-pro-max/scripts/search.py
- AuthenticationThrottlingTests
- BoutiqueManifestCompilationTests
- SuperLikePersistenceAndAttributionTests
- _validate_candidate
- UniversalLocalNetworkDevConfigurationTests
- 7. Background Queue & Worker Numbers
- InsufficientCandidatesError
- CatalogueQueueUnitTests
- Phase6BatchCRecentSessionsAndStreamingTests
- SessionDetailSerializer
- InteractionLogProcessingStatusTests
- Movie
- AdminCommandSecurityTests
- SessionPage.tsx
- Workflow Phases (Summary)
- Detailed Tasks
- AuthenticationAndPermissionTests
- MovieSerializer
- SettingsSecurityTests
- .agents/skills/ui-ux-pro-max/scripts/core.py
- StalePollerOwnershipError
- PasswordResetSecurityTests
- eslint.config.js
- diagnose_lan_connectivity.sh
- CandidateRetrievalAndEligibilityTests
- SessionJoiningTests
- dependencies
- Phase6BatchBBackendTests
- SwipeAndMatchingTests
- middleware.py
- LimitValidationTest
- SessionCodeCollisionTests
- 2xx — Successful Responses
- flick-frontend/package.json
- .poll
- devDependencies
- interface
- Examples
- SwipeUndoTests
- Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List
- GuestRecoveryAPITests
- EmailVerificationTests
- PreferencesPage.tsx
- .test_concurrent_duplicate_submissions_race_condition
- BM25
- BM25
- DiscoverTests
- TmdbChangesService
- MatchListFilteringSecurityTests
- AffinityEvaluationTests
- GuestConversionConcurrencyTests
- MotionAndSessionRegressionAuditTests
- vite.config.ts
- HealthCheckView
- 4xx — Client-Side Errors
- validate_movie_language
- SessionHistoryTests
- StaleLeaseOwnershipError
- PaginationAndResourceLimitTests
- RecommendationDiscoveryTests
- GuestRecoveryConcurrencyTests
- WatchlistTests
- Command
- vercel.json
- GuestActivityMiddleware
- Flick — HTTP Status Codes, Server Logs & Error-Handling Reference
- CorrectSyntheticM1RecordsTest
- verify-batch-b-browser.js
- SessionJoinView
- WatchlistDetailView
- SessionResetPreferencesView
- .test_concurrent_duplicate_submissions_by_single_user
- SessionCreateView
- parse_retry_after
- 5. Deep Dive: HTTP 304 Not Modified & Caching
- .reconcile
- 4. Deciphering Server Logs & Trailing Numbers
- TestIndianLanguageDiscovery
- IntelligenceModelsTestCase
- InMemoryTokenBucket
- test_observability_and_security.py
- DatabaseConcurrencyAndSwipeReliabilityTests
- Command
- DeckStateAPITests

## God Nodes (most connected - your core abstractions)
1. `Movie` - 209 edges
2. `Session` - 128 edges
3. `Genre` - 96 edges
4. `apiRequest()` - 76 edges
5. `UserPreferenceData` - 74 edges
6. `Swipe` - 71 edges
7. `HardConstraints` - 66 edges
8. `CollaborativeAgreement` - 60 edges
9. `InteractionLog` - 60 edges
10. `CatalogueJob` - 52 edges

## Surprising Connections (you probably didn't know these)
- `2. Secret Redaction Filter (`core/logging.py`)` --references--> `SecretRedactionFilter`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/logging.py
- `Anatomy of a Django/Daphne Access Log` --references--> `CorrelationIdMiddleware`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/middleware.py
- `Architecture & Data Decisions` --references--> `InteractionLog`  [INFERRED]
  tasks/plan.md → backend/core/models.py
- `Worker Leases, Fencing Tokens & Heartbeats` --references--> `StaleLeaseOwnershipError`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/catalogue_queue.py
- `Task 4: Guest Identity Linking Service` --references--> `IdentityLinkingService`  [INFERRED]
  tasks/plan.md → backend/core/services/identity_linking.py

## Import Cycles
- None detected.

## Communities (211 total, 110 thin omitted)

### Community 0 - "Batch3WorkerIntegrationTests"
Cohesion: 0.08
Nodes (3): _beat(), reset_handlers(), Batch3WorkerIntegrationTests

### Community 1 - "Defense-in-Depth Debugging Strategies"
Cohesion: 0.06
Nodes (30): Boundary Testing, Checkpoint: Layered debugging complete, Cleanup and teardown, Defense-in-Depth Debugging Strategies, Dependency isolation, Divide and Conquer, Hypothesis Testing Protocol, Input validation (+22 more)

### Community 2 - "compute_recovery_lookup_digest"
Cohesion: 0.04
Nodes (12): calculate_entropy_bits(), canonicalize_recovery_code(), compute_recovery_lookup_digest(), dummy_verify_recovery_code(), generate_recovery_code(), get_recovery_hmac_key(), hash_recovery_code(), verify_recovery_code() (+4 more)

### Community 3 - "django_db"
Cohesion: 0.04
Nodes (29): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+21 more)

### Community 4 - "_make_movie"
Cohesion: 0.11
Nodes (5): _guard_pass(), _make_movie(), _mock_tmdb_response(), QueueLifecycleAndProvenanceCorrectionTest, TMDBVerificationPipelineTest

### Community 5 - "router.tsx"
Cohesion: 0.13
Nodes (25): AccountSettingsPage, AnimatedRoutes(), AutoJoin, CreateSessionPage, DiscoverPage, EntryPage, ForgotPasswordPage, GuestConvertPage (+17 more)

### Community 6 - "GuestConversionValidationAndRejectionTests"
Cohesion: 0.07
Nodes (3): GuestConversionRecoverySecurityTests, GuestConversionSuccessTests, GuestConversionValidationAndRejectionTests

### Community 8 - "DiscoverPage.tsx"
Cohesion: 0.06
Nodes (31): Provider, ProviderLogo(), streamingCache, StreamingData, StreamingOptions(), ArchiveShelf, ArchiveShelfSection(), CatalogueSort (+23 more)

### Community 9 - "apiRequest"
Cohesion: 0.10
Nodes (31): 1. The `ApiError` Class, 3. Automatic Session Expiration Handling (401 Interceptor), 4. Empty States vs. Actual Errors, Frontend Error Handling (`api.ts` & React), AuthShell(), generateUsernameSuggestions(), getPasswordStrength(), STEPS (+23 more)

### Community 12 - "LocalizedGenreRetrievalTests"
Cohesion: 0.10
Nodes (3): LocalizedGenreRetrievalTests, fake_ingest(), fake_ingest()

### Community 13 - "CinemaHeader"
Cohesion: 0.08
Nodes (40): posthog-js@^1.319.0, BottomNav(), BottomNavProps, NavTab, CinemaHeader(), CinemaHeaderProps, trackEvent(), CreateSessionPage() (+32 more)

### Community 14 - "run_staleness_sweep"
Cohesion: 0.07
Nodes (5): Command, StalenessSweepCheckpoint, Meta, run_staleness_sweep(), StalenessSweepTests

### Community 16 - "DynamicMovieCatalogueTests"
Cohesion: 0.05
Nodes (15): CustomUserAdmin, GenreAdmin, MatchAdmin, MovieAdmin, MovieStreamingAvailabilityAdmin, SessionAdmin, SessionStatsAdmin, StreamingProviderAdmin (+7 more)

### Community 17 - "IntelligenceWorkerProcess"
Cohesion: 0.07
Nodes (4): Command, IntelligenceWorkerProcess, register_handler(), IntelligenceWorkerTasteHandlerTests

### Community 18 - "SessionPage.tsx"
Cohesion: 0.07
Nodes (42): DeckCardSkeleton(), MatchItemSkeleton(), MovieCardSkeleton(), ShelfSkeleton(), Skeleton(), SkeletonProps, StreamingItemSkeleton(), getWsBaseUrl() (+34 more)

### Community 19 - "compilerOptions"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+13 more)

### Community 20 - "CatalogueJob"
Cohesion: 0.17
Nodes (7): CatalogueJob, JobType, Meta, Status, handle_full_reconciliation(), handle_sync_changes_feed(), to_json_safe()

### Community 22 - "WebSocketRevocationTests"
Cohesion: 0.08
Nodes (8): broadcast_credential_revocation(), WebSocketRevocationTests, run(), run(), run(), run(), run(), run()

### Community 23 - "ProposalExecutionWorker"
Cohesion: 0.07
Nodes (5): Command, ProposalExecutionWorker, ProposalLifecycleAndIdempotencyTestCase, ProposalOutboxWorkerTestCase, ProposalOutboxProcessBatchView

### Community 24 - "Pre1990ReleasePeriodFilterTests"
Cohesion: 0.04
Nodes (3): ClassicVaultEraFilterTests, Pre1990ReleasePeriodFilterTests, SwipeFailureRecoveryAndEdgeCaseTests

### Community 26 - "permissions.py"
Cohesion: 0.15
Nodes (4): configure_sqlite_pragmas(), CoreConfig, CoreConfig, IsOwner

### Community 27 - "transition_movie_classification"
Cohesion: 0.07
Nodes (4): transition_movie_classification(), update_movie_metadata(), _validate_field_provenance_updates(), MovieMutationsTestCase

### Community 28 - "acquire_tmdb_token"
Cohesion: 0.09
Nodes (3): acquire_tmdb_token(), reset_rate_limiter(), TMDBRateLimiterInMemoryTests

### Community 29 - "Root Cause Tracing Techniques"
Cohesion: 0.07
Nodes (26): Checkpoint: When investigation is complete, Common Root Cause Patterns, Component Boundary Tracing, Configuration mismatch, Data Flow Analysis, Diff-based investigation, Error Message Anatomy, Example: Wrong calculation (+18 more)

### Community 30 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 31 - "RoomRecommendationScenariosTestCase"
Cohesion: 0.08
Nodes (4): CollaborativeDeckScorer, ScoredCandidate, compute_learned_feedback_from_logs(), RoomRecommendationScenariosTestCase

### Community 33 - "Systematic Debugging"
Cohesion: 0.12
Nodes (15): Do not use this skill when, Examples, First move, Guardrails, Inputs to gather, Outputs, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis (+7 more)

### Community 34 - "manifest.json"
Cohesion: 0.12
Nodes (16): background_color, categories, description, display, icons, lang, name, orientation (+8 more)

### Community 37 - "UserPreferenceData"
Cohesion: 0.05
Nodes (8): normalize_candidate_metadata(), rank_candidates_for_user(), IndividualRelevanceScorer, MovieIntelligenceData, ScoringConfig, ScoringResult, UserPreferenceData, ScoringServiceTestCase

### Community 40 - "backend/package.json"
Cohesion: 0.36
Nodes (7): devDependencies, autoprefixer@^10.4.23, postcss@^8.5.6, tailwindcss@^4.1.18, tailwindcss, autoprefixer, postcss

### Community 41 - "Genre"
Cohesion: 0.06
Nodes (11): Command, Command, Genre, GenreSerializer, Meta, ProposalOutboxMessageSerializer, Meta, SessionSerializer (+3 more)

### Community 42 - "views.py"
Cohesion: 0.04
Nodes (21): MovieTagRelation, Meta, StandardResultsSetPagination, SwipeHistoryPagination, RegisterSerializer, Meta, AuthRateThrottle, GuestProvisionThrottle (+13 more)

### Community 47 - "core/urls.py"
Cohesion: 0.03
Nodes (29): DeckSwipeUndoView, DeleteAccountView, ensure_default_genres(), GenreListView, GenreSyncTMDBView, GuestConvertView, GuestRecoveryAckView, MatchListView (+21 more)

### Community 48 - ".link_guest_to_user"
Cohesion: 0.11
Nodes (6): DuplicateIdentityLinkError, IdentityLinkingService, _resolve_user_actor_ids(), IdentityLinkingServiceTests, Checkpoint 2: Reconciliation & Identity Complete, Phase 2: Reconciliation & Identity

### Community 49 - "enrichment_handlers.py"
Cohesion: 0.15
Nodes (8): acquire_tmdb_token(), check_deterministic_identity(), handle_catalogue_classification(), handle_catalogue_enrichment(), is_synthetic_movie(), normalize_title(), record_tmdb_429(), _tmdb_api_get()

### Community 50 - ".agent/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 51 - "TestCase"
Cohesion: 0.10
Nodes (4): GenreIntegrationTests, LocalNetworkConfigurationTests, RecentSessionsTests, SessionLifecycleTests

### Community 54 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, lint, preview, test

### Community 55 - "6. Flick-Specific Error Handling Architecture"
Cohesion: 0.40
Nodes (5): 1. Custom Exception Handler (`backend/backend/exceptions.py`), 2. Secret Redaction Filter (`core/logging.py`), 3. Request Correlation ID Middleware (`core/middleware.py`), 6. Flick-Specific Error Handling Architecture, Backend Error Handling (DRF, Exceptions & Middleware)

### Community 56 - "3. Complete HTTP Status Code Guide"
Cohesion: 0.20
Nodes (10): 3. Complete HTTP Status Code Guide, 3xx — Redirection & Caching, 5xx — Server-Side & Upstream Errors, HTTP 301 Moved Permanently, HTTP 302 Found / Temporary Redirect, HTTP 304 Not Modified, HTTP 500 Internal Server Error, HTTP 502 Bad Gateway (+2 more)

### Community 57 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + TypeScript + Vite

### Community 59 - "tmdb.py"
Cohesion: 0.05
Nodes (34): recalculate_movie_eligibility(), discover_movies(), _fetch(), fetch_cached_tmdb(), format_tmdb_movie(), get_enhanced_movie_details(), get_genres_map(), get_movie_by_tmdb_id() (+26 more)

### Community 61 - "evaluate_eligibility_predicates"
Cohesion: 0.08
Nodes (5): MovieQuerySet, evaluate_eligibility_predicates(), EligibilityPredicatesOptionBTests, MovieEligibilityModelAndSignalTests, MovieQuerySetRestrictionTests

### Community 62 - "tmdb_rate_limiter.py"
Cohesion: 0.15
Nodes (9): calculate_cooldown_with_jitter(), get_rate_limiter_status(), get_redis_client(), is_production(), record_tmdb_429(), _redis_eval_acquire(), _redis_eval_record_429(), _redis_eval_status() (+1 more)

### Community 65 - "test_proposals.py"
Cohesion: 0.07
Nodes (9): ProposalError, ProposalExpiredError, ProposalInvalidStateError, ProposalNotFoundError, ProposalPermissionDeniedError, ProposalService, ProposalSupersededError, ProposalServiceTestCase (+1 more)

### Community 67 - "Session"
Cohesion: 0.04
Nodes (32): CollaborativeAgreement, Match, Meta, Session, SessionOccasionState, SessionStats, calculate_questionnaire_similarity(), calculate_screening_affinity() (+24 more)

### Community 69 - "django_db_models_deletion"
Cohesion: 0.06
Nodes (15): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+7 more)

### Community 70 - "ConstraintExpansionProposal"
Cohesion: 0.12
Nodes (6): ConstraintExpansionProposal, Meta, ConstraintExpansionProposalSerializer, Meta, ProposalDetailView, ProposalListCreateView

### Community 71 - "test_batch5_personalization.py"
Cohesion: 0.04
Nodes (33): InteractionLog, Meta, MovieExposure, MovieKeyword, MovieTag, UserIdentityLink, LinkType, Meta (+25 more)

### Community 72 - ".agent/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.20
Nodes (5): detect_domain(), _load_csv(), search(), _search_csv(), search_stack()

### Community 73 - "_assert_safe_local_database"
Cohesion: 0.16
Nodes (6): _assert_safe_local_database(), _resolve_canonical_db_path(), DryRunImmutabilityTest, SafetyGuardDebugFalseTest, SafetyGuardEngineTest, SafetyGuardPathTest

### Community 79 - "9. Practical Troubleshooting Playbook"
Cohesion: 0.12
Nodes (17): 10. `502 Bad Gateway`, 11. `503 Service Unavailable`, 12. `504 Gateway Timeout`, 13. `ConnectionResetError(54, 'Connection reset by peer')`, 14. `ECONNREFUSED 127.0.0.1:8000`, 15. `AbortError: The operation was aborted`, 16. `CatalogueJob status = failed_permanent`, 1. `200 55` (+9 more)

### Community 83 - "ConstraintExhaustionNoticeModal.tsx"
Cohesion: 0.22
Nodes (16): ConstraintExhaustionNoticeModal(), ConstraintExhaustionNoticeModalProps, ConstraintProposalData, DecisionInfo, parseDecision(), CANONICAL_ERAS, CANONICAL_GENRES, CANONICAL_LANGUAGES (+8 more)

### Community 84 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 86 - "api.ts"
Cohesion: 0.11
Nodes (29): RecoveryCodeModal(), RecoveryCodeModalProps, acknowledgeRecovery(), buildDeduplicationKey(), clearInFlightRequests(), convertGuestAccount(), getBaseUrl, getInFlightRequestCount() (+21 more)

### Community 88 - "HardConstraints"
Cohesion: 0.08
Nodes (5): ActiveManifestImmutableError, CandidatePool, HardConstraints, ManifestLearnedFeedbackIntegrationTests, ReproducibilityAndPersistenceTests

### Community 89 - "TmdbChangesCheckpoint"
Cohesion: 0.18
Nodes (3): TmdbChangesCheckpoint, Meta, PollTmdbChangesCommandTests

### Community 91 - "PostgreSQLQueueConcurrencyTests"
Cohesion: 0.12
Nodes (3): PostgreSQLQueueConcurrencyTests, do_enqueue(), worker_task()

### Community 92 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 93 - ".agents/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 94 - "ThemeContext.tsx"
Cohesion: 0.15
Nodes (14): App(), AppRouter(), RouteLoadingFallback(), CinematicLoader(), CinematicLoaderProps, FLICK_LOGOS, Theme, ThemeContext (+6 more)

### Community 95 - "UserIdentityLink"
Cohesion: 0.07
Nodes (3): handle_recompute_taste_profile(), recompute_user_taste_profile(), TasteEngineService

### Community 96 - "set_redis_client"
Cohesion: 0.10
Nodes (3): set_redis_client(), TMDBRateLimiterProductionFailClosedTests, TMDBRateLimiterRedisLuaMockTests

### Community 98 - "Swipe"
Cohesion: 0.05
Nodes (16): SessionChemistry, Meta, Swipe, Meta, UserTasteSignal, Meta, SwipeSerializer, Meta (+8 more)

### Community 99 - ".agent/skills/ui-ux-pro-max/scripts/search.py"
Cohesion: 0.11
Nodes (4): format_output(), format_output(), main(), start.sh script

### Community 102 - "BoutiqueManifestCompilationTests"
Cohesion: 0.11
Nodes (3): BoutiqueManifestCompilationTests, NormalManifestCompilationTests, ShortageRedistributionAndFloorTests

### Community 104 - "_validate_candidate"
Cohesion: 0.20
Nodes (3): Command, _validate_candidate(), CandidatePrevalidationTest

### Community 106 - "7. Background Queue & Worker Numbers"
Cohesion: 0.40
Nodes (5): 7. Background Queue & Worker Numbers, Queue Priorities & Fair Scheduling Quotas, Retry Limits, Exponential Backoff & Quarantine, TMDB Dual-Bucket Rate Limiter Constants, Worker Leases, Fencing Tokens & Heartbeats

### Community 107 - "InsufficientCandidatesError"
Cohesion: 0.08
Nodes (6): InsufficientCandidatesError, ManifestCompilationError, ReplenishmentInProgressError, TransientReplenishmentError, HamiltonManifestAllocatorTests, DeckCardDeliveryView

### Community 109 - "Phase6BatchCRecentSessionsAndStreamingTests"
Cohesion: 0.06
Nodes (10): Command, _make_session(), _tmdb_get(), fetch_tmdb_movies(), _create_tmdb_session(), get_tmdb_session(), reset_tmdb_session(), Phase6BatchCRecentSessionsAndStreamingTests (+2 more)

### Community 110 - "SessionDetailSerializer"
Cohesion: 0.09
Nodes (3): SessionDetailSerializer, Meta, SessionDetailView

### Community 112 - "Movie"
Cohesion: 0.08
Nodes (15): Command, Command, Command, Movie, MovieStreamingAvailability, Meta, StreamingProvider, movie_genres_changed_handler() (+7 more)

### Community 114 - "SessionPage.tsx"
Cohesion: 0.05
Nodes (39): 2. Automatic Error Message Extraction, ErrorBoundary, Props, State, ApiError, MenuItem(), ProfilePage(), ThemeToggleItem() (+31 more)

### Community 115 - "Workflow Phases (Summary)"
Cohesion: 0.25
Nodes (7): Common Rationalisations, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing, Phase 4: Implementation, Phases, Red Flags, and Common Rationalisations, Workflow Phases (Summary)

### Community 116 - "Detailed Tasks"
Cohesion: 0.22
Nodes (8): Architecture & Data Decisions, Detailed Tasks, Implementation Plan: Batch 4 — Historical Interaction Reconciliation and Identity Linking, Risks and Mitigations, Task 4: Guest Identity Linking Service, Task 5: Durable Taste Engine Service & Job Handler, Task 7: Comprehensive Verification & PostgreSQL Concurrency Tests, Work Breakdown & Dependencies

### Community 118 - "MovieSerializer"
Cohesion: 0.14
Nodes (5): MovieSerializer, Meta, CompleteCatalogueView, CuratorsSelectionView, YourArchiveView

### Community 120 - ".agents/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.21
Nodes (5): detect_domain(), _load_csv(), search(), _search_csv(), search_stack()

### Community 121 - "StalePollerOwnershipError"
Cohesion: 0.19
Nodes (4): Command, PollerLockedError, RateLimitBackoffError, StalePollerOwnershipError

### Community 123 - "eslint.config.js"
Cohesion: 0.15
Nodes (12): eslint@^9.39.1, @eslint/js@^9.39.1, eslint-plugin-react-hooks@^7.0.1, eslint-plugin-react-refresh@^0.4.24, globals@^16.5.0, typescript-eslint@^8.46.4, eslint, @eslint/js (+4 more)

### Community 127 - "dependencies"
Cohesion: 0.17
Nodes (12): dependencies, canvas-confetti@^1.9.4, framer-motion@^12.31.0, lucide-react@^0.577.0, material-symbols@^0.40.2, react@^19.2.0, react-dom@^19.2.0, react-router-dom@^7.12.0 (+4 more)

### Community 130 - "middleware.py"
Cohesion: 0.15
Nodes (3): get_user_from_token_key(), TokenAuthMiddleware, TokenAuthMiddlewareStack()

### Community 133 - "2xx — Successful Responses"
Cohesion: 0.40
Nodes (5): 2xx — Successful Responses, HTTP 200 OK, HTTP 201 Created, HTTP 202 Accepted, HTTP 204 No Content

### Community 134 - "flick-frontend/package.json"
Cohesion: 0.18
Nodes (10): @types/canvas-confetti@^1.9.0, @types/node@^24.10.1, typescript@~5.9.3, name, private, type, version, @types/canvas-confetti (+2 more)

### Community 136 - "devDependencies"
Cohesion: 0.14
Nodes (13): devDependencies, jsdom@^30.1.3, tailwindcss@^4.1.18, @testing-library/jest-dom@^7.0.1, @testing-library/react@^16.3.3, @types/react@^19.2.5, @types/react-dom@^19.2.3, vitest@^5.1.0 (+5 more)

### Community 137 - "interface"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 139 - "Examples"
Cohesion: 0.40
Nodes (4): Example 1: Test failure with stack trace, Example 2: Intermittent test failure, Example 3: Regression after a commit, Examples

### Community 141 - "Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List"
Cohesion: 0.50
Nodes (3): Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List, Checkpoint 3: Batch 4 Complete, Phase 3: Durable Taste Engine & Tombstone Anonymization

### Community 142 - "GuestRecoveryAPITests"
Cohesion: 0.05
Nodes (5): ExistingRegisteredUserCompatibilityTests, GuestProvisioningAPITests, GuestRecoveryAPITests, GuestThrottlingTests, RecoveryHandoffReliabilityTests

### Community 144 - "PreferencesPage.tsx"
Cohesion: 0.14
Nodes (14): OptionIcon(), PreferencesPage(), buildPreferences(), checkSessionState(), handleNext(), handleSubmit(), loadAuthoritativeState(), Question (+6 more)

### Community 165 - "vite.config.ts"
Cohesion: 0.22
Nodes (6): @tailwindcss/vite@^4.1.18, vite@^7.2.4, @vitejs/plugin-react@^5.1.1, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 167 - "4xx — Client-Side Errors"
Cohesion: 0.17
Nodes (12): 4xx — Client-Side Errors, HTTP 400 Bad Request, HTTP 401 Unauthorized, HTTP 403 Forbidden, HTTP 404 Not Found, HTTP 405 Method Not Allowed, HTTP 408 Request Timeout, HTTP 409 Conflict (+4 more)

### Community 170 - "StaleLeaseOwnershipError"
Cohesion: 0.29
Nodes (3): CatalogueQueueError, JobNotFoundError, StaleLeaseOwnershipError

### Community 178 - "Flick — HTTP Status Codes, Server Logs & Error-Handling Reference"
Cohesion: 0.20
Nodes (9): 10. Glossary of Key Technical Terms, 1. Quick-Reference Cheat Sheet, 2. What Are HTTP Status Codes?, 8. Frontend & Build-Related Numbers, At a Glance: What Do These Numbers Mean?, Flick — HTTP Status Codes, Server Logs & Error-Handling Reference, Port Numbers, Table of Contents (+1 more)

### Community 179 - "CorrectSyntheticM1RecordsTest"
Cohesion: 0.11
Nodes (6): Command, _inspect_target_records(), _resolve_staff_user(), _build_candidate_queryset(), CorrectSyntheticM1RecordsTest, _guard_pass()

### Community 180 - "verify-batch-b-browser.js"
Cohesion: 0.21
Nodes (5): puppeteer-core@^25.16.0, SCREENSHOT_DIR, SCREENSHOT_DIR, SCREENSHOT_DIR, puppeteer-core

### Community 197 - "5. Deep Dive: HTTP 304 Not Modified & Caching"
Cohesion: 0.40
Nodes (5): 5. Deep Dive: HTTP 304 Not Modified & Caching, Conditional Requests (ETag & Last-Modified), How Browser Caching Works, How Caching Is Implemented in Flick, When 304 Is Healthy vs When It Is a Problem

### Community 201 - ".reconcile"
Cohesion: 0.13
Nodes (3): Command, map_swipe_reaction(), reconcile_historical_interactions()

### Community 204 - "4. Deciphering Server Logs & Trailing Numbers"
Cohesion: 0.29
Nodes (7): 4. Deciphering Server Logs & Trailing Numbers, Anatomy of a Django/Daphne Access Log, What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery), Why does `/api/curators-selection/` show `200 1989`?, Why does `/api/users/profile/` show `200 55`?, Why does `GET /api/movies/` show `304 -` or `304 0`?, WSGI vs ASGI Logging Differences

### Community 205 - "TestIndianLanguageDiscovery"
Cohesion: 0.08
Nodes (4): DiscoveryQuerySpec, IndianCatalogueCoverageReport, IndianCatalogueDiscoveryService, TestIndianLanguageDiscovery

### Community 211 - "InMemoryTokenBucket"
Cohesion: 0.15
Nodes (5): InMemoryTokenBucket, 1. The Movie Database (TMDB), 2. Redis, 3. PostgreSQL & SQLite, External Service Failure Modes (TMDB, Redis, Postgres)

### Community 219 - "test_observability_and_security.py"
Cohesion: 0.04
Nodes (17): CorrelationIdFilter, get_correlation_id(), reset_correlation_id(), SecretRedactionFilter, SecretRedactionFormatter, set_correlation_id(), CorrelationIdMiddleware, Migration (+9 more)

## Knowledge Gaps
- **110 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Movie` connect `Movie` to `Batch3WorkerIntegrationTests`, `Phase6BatchBBackendTests`, `SwipeAndMatchingTests`, `django_db`, `LimitValidationTest`, `_make_movie`, `HardConstraintFilter`, `TmdbChangesServiceTests`, `LocalizedGenreRetrievalTests`, `SwipeUndoTests`, `run_staleness_sweep`, `Batch5PersonalizationEvaluationTests`, `DynamicMovieCatalogueTests`, `DeckStateAPITests`, `IntelligenceWorkerProcess`, `Stage3EndToEndProductValidationTests`, `ProposalExecutionWorker`, `Pre1990ReleasePeriodFilterTests`, `TmdbChangesService`, `SessionLifecycleAndQuestionnaireRecoveryTests`, `transition_movie_classification`, `DiscoverTests`, `MatchListFilteringSecurityTests`, `RoomRecommendationScenariosTestCase`, `AffinityEvaluationTests`, `MotionAndSessionRegressionAuditTests`, `UserPreferenceData`, `StreamingFilterAuditTests`, `Genre`, `SessionHistoryTests`, `UserProfile`, `TestReliabilityAndRetrieval`, `ScreeningSessionResultsAndStatsPersistenceTests`, `PaginationAndResourceLimitTests`, `Command`, `RecommendationDiscoveryTests`, `enrichment_handlers.py`, `WatchlistTests`, `CorrectSyntheticM1RecordsTest`, `core/urls.py`, `Batch2EnrichmentAndWorkerTests`, `tmdb.py`, `evaluate_eligibility_predicates`, `TMDBTimeoutError`, `Session`, `test_batch5_personalization.py`, `_assert_safe_local_database`, `TestIndianLanguageDiscovery`, `IntelligenceModelsTestCase`, `ArchiveShelvesService`, `SuperLikeReactionMatrixIntegrationTests`, `views.py`, `.anonymize_and_delete_user`, `HardConstraints`, `TmdbChangesCheckpoint`, `PostgreSQLQueueConcurrencyTests`, `Swipe`, `BoutiqueManifestCompilationTests`, `SuperLikePersistenceAndAttributionTests`, `_validate_candidate`, `Phase6BatchCRecentSessionsAndStreamingTests`, `InteractionLogProcessingStatusTests`, `DatabaseConcurrencyAndSwipeReliabilityTests`, `AuthenticationAndPermissionTests`, `MovieSerializer`, `CandidateRetrievalAndEligibilityTests`?**
  _High betweenness centrality (0.244) - this node is a cross-community bridge._
- **Are the 130 inferred relationships involving `Movie` (e.g. with `Command` and `Command`) actually correct?**
  _`Movie` has 130 INFERRED edges - model-reasoned connections that need verification._
- **Should `Batch3WorkerIntegrationTests` be split into smaller, more focused modules?**
  _Cohesion score 0.0784313725490196 - nodes in this community are weakly interconnected._
- **Why does `Frontend Error Handling (`api.ts` & React)` connect `apiRequest` to `SessionPage.tsx`, `6. Flick-Specific Error Handling Architecture`?**
  _High betweenness centrality (0.153) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `Session` (e.g. with `MatchConsumer` and `SessionDetailSerializer`) actually correct?**
  _`Session` has 79 INFERRED edges - model-reasoned connections that need verification._
- **Should `Defense-in-Depth Debugging Strategies` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Why does `6. Flick-Specific Error Handling Architecture` connect `6. Flick-Specific Error Handling Architecture` to `apiRequest`, `Flick — HTTP Status Codes, Server Logs & Error-Handling Reference`, `InMemoryTokenBucket`?**
  _High betweenness centrality (0.153) - this node is a cross-community bridge._