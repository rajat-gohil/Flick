# Graph Report - flick-app  (2026-11-17)

## Corpus Check
- 247 files · ~374,020 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 59 file(s) not represented in the graph (top: .csv 48, (none) 7, .example 2)

## Summary
- 4250 nodes · 9203 edges · 191 communities (98 shown, 93 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1049 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `224df542`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- PersonalizedRecommendationEngine
- Defense-in-Depth Debugging Strategies
- canonicalize_recovery_code
- django_db
- _make_movie
- router.tsx
- GuestConversionValidationAndRejectionTests
- WebSocketAuthenticationAndAuthorizationTests
- DiscoverPage.tsx
- apiRequest
- handle_catalogue_classification
- SessionPage.tsx
- batch3_handlers.py
- CinemaHeader
- MovieSerializer
- Batch5PersonalizationEvaluationTests
- DynamicMovieCatalogueTests
- get_correlation_id
- HomePage.tsx
- compilerOptions
- ConstraintExhaustionNoticeModal.tsx
- Stage3EndToEndProductValidationTests
- WebSocketRevocationTests
- ProposalExecutionWorker
- Pre1990ReleasePeriodFilterTests
- SessionLifecycleAndQuestionnaireRecoveryTests
- permissions.py
- transition_movie_classification
- CatalogueJob
- Root Cause Tracing Techniques
- compilerOptions
- TMDBRateLimiterInMemoryTests
- MatchConsumer
- Systematic Debugging
- manifest.json
- ProposalAPITestCase
- Command
- RecommendationDiscoveryTests
- evaluate_eligibility_predicates
- ProfilePage.tsx
- backend/package.json
- test_recommendation_evaluation.py
- .record_swipe_response
- UndoNotPermittedError
- admin.py
- ScreeningSessionResultsAndStatsPersistenceTests
- DesignSystemGenerator
- views.py
- .link_guest_to_user
- _ingest_tmdb_results
- .agent/skills/ui-ux-pro-max/scripts/design_system.py
- TestCase
- DesignSystemGenerator
- GuestSecurityHMACAndVerificationTests
- scripts
- 6. Flick-Specific Error Handling Architecture
- 3. Complete HTTP Status Code Guide
- React + TypeScript + Vite
- vercel.json
- tmdb.py
- .enqueue
- CorrelationIdMiddleware
- tmdb.py
- sw.js
- DeckStateError
- test_proposals.py
- tsconfig.json
- retrieval.py
- GuestActivityTrackingTests
- StreamingProvider
- update_movie_metadata
- Swipe
- .agent/skills/ui-ux-pro-max/scripts/core.py
- MovieTagRelation
- 9. Practical Troubleshooting Playbook
- batch_sync_prelaunch.py
- ArchiveShelvesService
- Movie
- TmdbChangesService
- ui-ux-pro-max
- .anonymize_and_delete_user
- api.ts
- UserIdentityLinkModelTests
- LocalizedGenreRetrievalTests
- GuestSecurityHMACAndVerificationTests
- PasswordResetSecurityTests
- PostgreSQLQueueConcurrencyTests
- ui-ux-pro-max
- .agents/skills/ui-ux-pro-max/scripts/design_system.py
- HardConstraintFilter
- .recompute_user_taste_profile
- set_redis_client
- TestReliabilityAndRetrieval
- AuthenticationAndPermissionTests
- .agent/skills/ui-ux-pro-max/scripts/search.py
- AuthenticationThrottlingTests
- CorrelationIdConcurrencyTests
- StreamingFilterAuditTests
- .generate_targeted_discovery_plan
- UniversalLocalNetworkDevConfigurationTests
- 7. Background Queue & Worker Numbers
- .calculate_allocation
- Phase6BatchCTMDBReliabilityTests
- SessionDetailSerializer
- Phase1EndToEndScenarioTestCase
- SuperLikeReactionMatrixIntegrationTests
- AdminCommandSecurityTests
- SessionPage.tsx
- Workflow Phases (Summary)
- SessionJoiningTests
- UserPreferenceData
- SwipeUndoTests
- SettingsSecurityTests
- RecoveryHandoffReliabilityTests
- GuestProfileModelTests
- BM25
- BM25
- diagnose_lan_connectivity.sh
- CandidateRetrievalAndEligibilityTests
- CoreUserExperienceRepairTests
- _validate_candidate
- Phase6BatchBBackendTests
- SwipeAndMatchingTests
- middleware.py
- SessionCodeCollisionTests
- DeckCardDeliveryView
- PaginationAndResourceLimitTests
- eslint.config.js
- interface
- PasswordResetSecurityTests
- Examples
- SwipeSerializer
- InteractionLogProcessingStatusTests
- EmailVerificationTests
- dependencies
- .handle
- Match
- devDependencies
- Command
- _build_candidate_queryset
- AuthRateThrottle
- GuestActivityMiddleware
- DiscoverTests
- CuratorsSelectionView
- Command
- GuestSecurityCryptoTests
- .test_concurrent_duplicate_submissions_by_single_user
- .test_concurrent_duplicate_submissions_race_condition
- MatchListFilteringSecurityTests
- SessionSetPreferencesView
- .test_concurrent_http_asgi_requests_through_middleware
- GuestConversionConcurrencyTests
- GenreIntegrationTests
- WorkflowEndToEndIntegrationTests
- 4xx — Client-Side Errors
- flick-frontend/package.json
- Flick — HTTP Status Codes, Server Logs & Error-Handling Reference
- CorrectSyntheticM1RecordsTest
- verify-batch-b-browser.js
- 2xx — Successful Responses
- vite.config.ts
- WatchlistItem
- parse_retry_after
- 5. Deep Dive: HTTP 304 Not Modified & Caching
- GuestProvisioningAPITests
- Swipe
- 4. Deciphering Server Logs & Trailing Numbers
- TestIndianLanguageDiscovery
- IntelligenceModelsTestCase
- InMemoryTokenBucket
- SecretRedactionFilter
- .compile_manifest
- SuperLikePersistenceAndAttributionTests
- DatabaseConcurrencyAndSwipeReliabilityTests
- run_staleness_sweep
- MotionAndSessionRegressionAuditTests
- SessionHistoryTests
- requests
- DeckStateAPITests

## God Nodes (most connected - your core abstractions)
1. `Movie` - 209 edges
2. `Session` - 128 edges
3. `Genre` - 96 edges
4. `apiRequest()` - 75 edges
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
- `Worker Leases, Fencing Tokens & Heartbeats` --references--> `StaleLeaseOwnershipError`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/catalogue_queue.py
- `HTTP 403 Forbidden` --references--> `transition_movie_classification()`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/movie_mutations.py
- `HTTP 429 Too Many Requests` --references--> `AuthRateThrottle`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/throttling.py

## Import Cycles
- None detected.

## Communities (191 total, 93 thin omitted)

### Community 1 - "Defense-in-Depth Debugging Strategies"
Cohesion: 0.06
Nodes (30): Boundary Testing, Checkpoint: Layered debugging complete, Cleanup and teardown, Defense-in-Depth Debugging Strategies, Dependency isolation, Divide and Conquer, Hypothesis Testing Protocol, Input validation (+22 more)

### Community 3 - "django_db"
Cohesion: 0.02
Nodes (47): calculate_entropy_bits(), compute_recovery_lookup_digest(), dummy_verify_recovery_code(), generate_recovery_code(), hash_recovery_code(), verify_recovery_code(), Migration, Migration (+39 more)

### Community 4 - "_make_movie"
Cohesion: 0.06
Nodes (12): _assert_safe_local_database(), _resolve_canonical_db_path(), DryRunImmutabilityTest, _guard_pass(), LimitValidationTest, _make_movie(), _mock_tmdb_response(), QueueLifecycleAndProvenanceCorrectionTest (+4 more)

### Community 5 - "router.tsx"
Cohesion: 0.13
Nodes (25): AccountSettingsPage, AnimatedRoutes(), AutoJoin, CreateSessionPage, DiscoverPage, EntryPage, ForgotPasswordPage, GuestConvertPage (+17 more)

### Community 6 - "GuestConversionValidationAndRejectionTests"
Cohesion: 0.06
Nodes (4): GuestConversionDataIntegrityTests, GuestConversionRecoverySecurityTests, GuestConversionSuccessTests, GuestConversionValidationAndRejectionTests

### Community 8 - "DiscoverPage.tsx"
Cohesion: 0.06
Nodes (31): Provider, ProviderLogo(), streamingCache, StreamingData, StreamingOptions(), ArchiveShelf, ArchiveShelfSection(), CatalogueSort (+23 more)

### Community 9 - "apiRequest"
Cohesion: 0.12
Nodes (29): 1. The `ApiError` Class, 2. Automatic Error Message Extraction, 3. Automatic Session Expiration Handling (401 Interceptor), 4. Empty States vs. Actual Errors, Frontend Error Handling (`api.ts` & React), AuthShell(), generateUsernameSuggestions(), getPasswordStrength() (+21 more)

### Community 10 - "handle_catalogue_classification"
Cohesion: 0.08
Nodes (9): acquire_tmdb_token(), check_deterministic_identity(), handle_catalogue_classification(), handle_catalogue_enrichment(), is_synthetic_movie(), normalize_title(), record_tmdb_429(), _tmdb_api_get() (+1 more)

### Community 11 - "SessionPage.tsx"
Cohesion: 0.07
Nodes (42): DeckCardSkeleton(), MatchItemSkeleton(), MovieCardSkeleton(), ShelfSkeleton(), Skeleton(), SkeletonProps, StreamingItemSkeleton(), getWsBaseUrl() (+34 more)

### Community 12 - "batch3_handlers.py"
Cohesion: 0.10
Nodes (5): reset_handlers(), handle_full_reconciliation(), handle_sync_changes_feed(), to_json_safe(), IntelligenceWorkerTasteHandlerTests

### Community 13 - "CinemaHeader"
Cohesion: 0.13
Nodes (25): BottomNav(), BottomNavProps, NavTab, CinemaHeader(), CinemaHeaderProps, AccountSettingsPage(), handleChangeEmail(), handleChangePassword() (+17 more)

### Community 14 - "MovieSerializer"
Cohesion: 0.08
Nodes (13): SessionChemistry, Meta, UserTasteSignal, Meta, MovieSerializer, Meta, calculate_preference_score(), MovieCreateView (+5 more)

### Community 16 - "DynamicMovieCatalogueTests"
Cohesion: 0.05
Nodes (3): DynamicMovieCatalogueTests, FunctionalAndMobileAuditVerificationTests, StreamingProviderAvailabilityTests

### Community 17 - "get_correlation_id"
Cohesion: 0.12
Nodes (3): get_correlation_id(), CorrelationIdMiddlewareTests, failing_view()

### Community 18 - "HomePage.tsx"
Cohesion: 0.06
Nodes (35): posthog-js@^1.319.0, trackEvent(), CreateSessionPage(), createSession(), Genre, getGenreIcon(), Industry, INDUSTRY_OPTIONS (+27 more)

### Community 19 - "compilerOptions"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+13 more)

### Community 20 - "ConstraintExhaustionNoticeModal.tsx"
Cohesion: 0.22
Nodes (16): ConstraintExhaustionNoticeModal(), ConstraintExhaustionNoticeModalProps, ConstraintProposalData, DecisionInfo, parseDecision(), CANONICAL_ERAS, CANONICAL_GENRES, CANONICAL_LANGUAGES (+8 more)

### Community 22 - "WebSocketRevocationTests"
Cohesion: 0.08
Nodes (8): broadcast_credential_revocation(), WebSocketRevocationTests, run(), run(), run(), run(), run(), run()

### Community 23 - "ProposalExecutionWorker"
Cohesion: 0.05
Nodes (9): Command, ActiveManifestImmutableError, ProposalExecutionWorker, CandidatePool, HardConstraints, ManifestLearnedFeedbackIntegrationTests, ReproducibilityAndPersistenceTests, ProposalLifecycleAndIdempotencyTestCase (+1 more)

### Community 24 - "Pre1990ReleasePeriodFilterTests"
Cohesion: 0.04
Nodes (3): ClassicVaultEraFilterTests, Pre1990ReleasePeriodFilterTests, SwipeFailureRecoveryAndEdgeCaseTests

### Community 26 - "permissions.py"
Cohesion: 0.15
Nodes (4): configure_sqlite_pragmas(), CoreConfig, CoreConfig, IsOwner

### Community 28 - "CatalogueJob"
Cohesion: 0.07
Nodes (18): Command, register_handler(), CatalogueJob, JobType, Meta, Status, TmdbChangesCheckpoint, Meta (+10 more)

### Community 29 - "Root Cause Tracing Techniques"
Cohesion: 0.07
Nodes (26): Checkpoint: When investigation is complete, Common Root Cause Patterns, Component Boundary Tracing, Configuration mismatch, Data Flow Analysis, Diff-based investigation, Error Message Anatomy, Example: Wrong calculation (+18 more)

### Community 30 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 31 - "TMDBRateLimiterInMemoryTests"
Cohesion: 0.09
Nodes (3): acquire_tmdb_token(), reset_rate_limiter(), TMDBRateLimiterInMemoryTests

### Community 33 - "Systematic Debugging"
Cohesion: 0.12
Nodes (15): Do not use this skill when, Examples, First move, Guardrails, Inputs to gather, Outputs, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis (+7 more)

### Community 34 - "manifest.json"
Cohesion: 0.12
Nodes (16): background_color, categories, description, display, icons, lang, name, orientation (+8 more)

### Community 38 - "evaluate_eligibility_predicates"
Cohesion: 0.06
Nodes (7): validate_movie_language(), MovieQuerySet, evaluate_eligibility_predicates(), EligibilityPredicatesOptionBTests, LanguageValidationTests, MovieEligibilityModelAndSignalTests, MovieQuerySetRestrictionTests

### Community 39 - "ProfilePage.tsx"
Cohesion: 0.14
Nodes (16): App(), AppRouter(), RouteLoadingFallback(), CinematicLoader(), CinematicLoaderProps, FLICK_LOGOS, Theme, ThemeContext (+8 more)

### Community 40 - "backend/package.json"
Cohesion: 0.36
Nodes (7): devDependencies, autoprefixer@^10.4.23, postcss@^8.5.6, tailwindcss@^4.1.18, tailwindcss, autoprefixer, postcss

### Community 41 - "test_recommendation_evaluation.py"
Cohesion: 0.07
Nodes (11): MovieExposure, compute_cohort_divergence(), compute_negative_response_rate(), compute_preference_alignment(), compute_shelf_diversity(), compute_unexposed_discovery_ratio(), _extract_movie_id(), _extract_movie_tokens() (+3 more)

### Community 44 - "admin.py"
Cohesion: 0.20
Nodes (11): CustomUserAdmin, GenreAdmin, MatchAdmin, MovieAdmin, MovieStreamingAvailabilityAdmin, SessionAdmin, SessionStatsAdmin, StreamingProviderAdmin (+3 more)

### Community 47 - "views.py"
Cohesion: 0.03
Nodes (40): StandardResultsSetPagination, SwipeHistoryPagination, DeckSwipeUndoView, DeleteAccountView, ensure_default_genres(), generate_session_code(), GenreListView, GenreSyncTMDBView (+32 more)

### Community 50 - ".agent/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 51 - "TestCase"
Cohesion: 0.09
Nodes (4): LocalNetworkConfigurationTests, RecentSessionsTests, SessionLifecycleTests, WatchlistTests

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

### Community 58 - "vercel.json"
Cohesion: 0.50
Nodes (3): cleanUrls, rewrites, $schema

### Community 59 - "tmdb.py"
Cohesion: 0.04
Nodes (37): discover_movies(), _fetch(), fetch_cached_tmdb(), format_tmdb_movie(), get_enhanced_movie_details(), get_genres_map(), get_movie_by_tmdb_id(), _fetch() (+29 more)

### Community 60 - ".enqueue"
Cohesion: 0.04
Nodes (4): IntelligenceWorkerProcess, _beat(), Batch3WorkerIntegrationTests, CatalogueQueueUnitTests

### Community 61 - "CorrelationIdMiddleware"
Cohesion: 0.22
Nodes (3): reset_correlation_id(), set_correlation_id(), CorrelationIdMiddleware

### Community 62 - "tmdb.py"
Cohesion: 0.15
Nodes (9): calculate_cooldown_with_jitter(), get_rate_limiter_status(), get_redis_client(), is_production(), record_tmdb_429(), _redis_eval_acquire(), _redis_eval_record_429(), _redis_eval_status() (+1 more)

### Community 64 - "DeckStateError"
Cohesion: 0.19
Nodes (6): ConflictingResponseError, DeckStateError, InvalidCardIndexError, OutOfOrderResponseError, StaleManifestError, DeckSwipeResponseView

### Community 65 - "test_proposals.py"
Cohesion: 0.05
Nodes (18): ConstraintExpansionProposal, Meta, Session, ConstraintExpansionProposalSerializer, Meta, SessionSerializer, Meta, ProposalError (+10 more)

### Community 67 - "retrieval.py"
Cohesion: 0.08
Nodes (20): CollaborativeAgreement, SessionOccasionState, SessionStats, calculate_questionnaire_similarity(), calculate_screening_affinity(), calculate_session_statistics(), calculate_taste_compatibility(), normalize_user_preferences() (+12 more)

### Community 69 - "StreamingProvider"
Cohesion: 0.09
Nodes (6): Command, Command, MovieStreamingAvailability, Meta, StreamingProvider, Phase6BatchCRecentSessionsAndStreamingTests

### Community 71 - "Swipe"
Cohesion: 0.04
Nodes (38): GuestProfile, Meta, InteractionLog, Meta, MovieKeyword, MovieTag, UserIdentityLink, LinkType (+30 more)

### Community 72 - ".agent/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.11
Nodes (10): detect_domain(), _load_csv(), search(), _search_csv(), search_stack(), detect_domain(), _load_csv(), search() (+2 more)

### Community 73 - "MovieTagRelation"
Cohesion: 0.16
Nodes (4): MovieTagRelation, Meta, RegisterSerializer, Meta

### Community 79 - "9. Practical Troubleshooting Playbook"
Cohesion: 0.12
Nodes (17): 10. `502 Bad Gateway`, 11. `503 Service Unavailable`, 12. `504 Gateway Timeout`, 13. `ConnectionResetError(54, 'Connection reset by peer')`, 14. `ECONNREFUSED 127.0.0.1:8000`, 15. `AbortError: The operation was aborted`, 16. `CatalogueJob status = failed_permanent`, 1. `200 55` (+9 more)

### Community 80 - "batch_sync_prelaunch.py"
Cohesion: 0.21
Nodes (3): Command, _make_session(), _tmdb_get()

### Community 82 - "Movie"
Cohesion: 0.06
Nodes (17): Command, Command, Genre, Movie, GenreSerializer, Meta, movie_genres_changed_handler(), recalculate_movie_eligibility() (+9 more)

### Community 84 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 86 - "api.ts"
Cohesion: 0.10
Nodes (30): RecoveryCodeModal(), RecoveryCodeModalProps, acknowledgeRecovery(), ApiError, buildDeduplicationKey(), clearInFlightRequests(), convertGuestAccount(), getBaseUrl (+22 more)

### Community 88 - "LocalizedGenreRetrievalTests"
Cohesion: 0.09
Nodes (3): LocalizedGenreRetrievalTests, fake_ingest(), fake_ingest()

### Community 91 - "PostgreSQLQueueConcurrencyTests"
Cohesion: 0.12
Nodes (3): PostgreSQLQueueConcurrencyTests, do_enqueue(), worker_task()

### Community 92 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 93 - ".agents/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 96 - "set_redis_client"
Cohesion: 0.10
Nodes (3): set_redis_client(), TMDBRateLimiterProductionFailClosedTests, TMDBRateLimiterRedisLuaMockTests

### Community 99 - ".agent/skills/ui-ux-pro-max/scripts/search.py"
Cohesion: 0.11
Nodes (4): format_output(), format_output(), main(), start.sh script

### Community 102 - "CorrelationIdConcurrencyTests"
Cohesion: 0.20
Nodes (4): CorrelationIdConcurrencyTests, run_all(), worker(), TMDBOutboundHeaderPropagationTests

### Community 106 - "7. Background Queue & Worker Numbers"
Cohesion: 0.40
Nodes (5): 7. Background Queue & Worker Numbers, Queue Priorities & Fair Scheduling Quotas, Retry Limits, Exponential Backoff & Quarantine, TMDB Dual-Bucket Rate Limiter Constants, Worker Leases, Fencing Tokens & Heartbeats

### Community 109 - "Phase6BatchCTMDBReliabilityTests"
Cohesion: 0.24
Nodes (3): _create_tmdb_session(), get_tmdb_session(), worker()

### Community 110 - "SessionDetailSerializer"
Cohesion: 0.05
Nodes (3): SessionDetailSerializer, Meta, AffinityEvaluationTests

### Community 112 - "SuperLikeReactionMatrixIntegrationTests"
Cohesion: 0.16
Nodes (3): submit_guest(), submit_host(), SuperLikeReactionMatrixIntegrationTests

### Community 114 - "SessionPage.tsx"
Cohesion: 0.05
Nodes (31): ErrorBoundary, Props, State, SessionPage(), AvatarStack(), RecentSession, SessionCard(), SessionsListPage() (+23 more)

### Community 115 - "Workflow Phases (Summary)"
Cohesion: 0.25
Nodes (7): Common Rationalisations, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing, Phase 4: Implementation, Phases, Red Flags, and Common Rationalisations, Workflow Phases (Summary)

### Community 117 - "UserPreferenceData"
Cohesion: 0.05
Nodes (8): CollaborativeDeckScorer, normalize_candidate_metadata(), rank_candidates_for_user(), IndividualRelevanceScorer, MovieIntelligenceData, UserPreferenceData, RoomRecommendationScenariosTestCase, ScoringServiceTestCase

### Community 130 - "middleware.py"
Cohesion: 0.16
Nodes (3): get_user_from_token_key(), TokenAuthMiddleware, TokenAuthMiddlewareStack()

### Community 133 - "DeckCardDeliveryView"
Cohesion: 0.25
Nodes (4): ManifestCompilationError, ReplenishmentInProgressError, TransientReplenishmentError, DeckCardDeliveryView

### Community 136 - "eslint.config.js"
Cohesion: 0.15
Nodes (12): eslint@^9.39.1, @eslint/js@^9.39.1, eslint-plugin-react-hooks@^7.0.1, eslint-plugin-react-refresh@^0.4.24, globals@^16.5.0, typescript-eslint@^8.46.4, eslint, @eslint/js (+4 more)

### Community 137 - "interface"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 139 - "Examples"
Cohesion: 0.40
Nodes (4): Example 1: Test failure with stack trace, Example 2: Intermittent test failure, Example 3: Regression after a commit, Examples

### Community 140 - "SwipeSerializer"
Cohesion: 0.29
Nodes (4): SwipeSerializer, Meta, _safe_analytics_callback(), SwipeCreateView

### Community 144 - "dependencies"
Cohesion: 0.17
Nodes (12): dependencies, canvas-confetti@^1.9.4, framer-motion@^12.31.0, lucide-react@^0.577.0, material-symbols@^0.40.2, react@^19.2.0, react-dom@^19.2.0, react-router-dom@^7.12.0 (+4 more)

### Community 146 - "Match"
Cohesion: 0.08
Nodes (7): Match, Meta, ConcurrencyAndAtomicityTests, SessionQueryOptimizationTests, compute_session_statistics(), serialize_session_matches(), SwipeUndoView

### Community 147 - "devDependencies"
Cohesion: 0.14
Nodes (13): devDependencies, jsdom@^30.1.3, tailwindcss@^4.1.18, @testing-library/jest-dom@^7.0.1, @testing-library/react@^16.3.3, @types/react@^19.2.5, @types/react-dom@^19.2.3, vitest@^5.1.0 (+5 more)

### Community 150 - "AuthRateThrottle"
Cohesion: 0.18
Nodes (5): AuthRateThrottle, GuestProvisionThrottle, GuestRecoverThrottle, PasswordResetRateThrottle, LoginView

### Community 167 - "4xx — Client-Side Errors"
Cohesion: 0.17
Nodes (12): 4xx — Client-Side Errors, HTTP 400 Bad Request, HTTP 401 Unauthorized, HTTP 403 Forbidden, HTTP 404 Not Found, HTTP 405 Method Not Allowed, HTTP 408 Request Timeout, HTTP 409 Conflict (+4 more)

### Community 171 - "flick-frontend/package.json"
Cohesion: 0.18
Nodes (10): @types/canvas-confetti@^1.9.0, @types/node@^24.10.1, typescript@~5.9.3, name, private, type, version, @types/canvas-confetti (+2 more)

### Community 178 - "Flick — HTTP Status Codes, Server Logs & Error-Handling Reference"
Cohesion: 0.20
Nodes (9): 10. Glossary of Key Technical Terms, 1. Quick-Reference Cheat Sheet, 2. What Are HTTP Status Codes?, 8. Frontend & Build-Related Numbers, At a Glance: What Do These Numbers Mean?, Flick — HTTP Status Codes, Server Logs & Error-Handling Reference, Port Numbers, Table of Contents (+1 more)

### Community 179 - "CorrectSyntheticM1RecordsTest"
Cohesion: 0.19
Nodes (3): _resolve_staff_user(), CorrectSyntheticM1RecordsTest, _guard_pass()

### Community 180 - "verify-batch-b-browser.js"
Cohesion: 0.21
Nodes (5): puppeteer-core@^25.16.0, SCREENSHOT_DIR, SCREENSHOT_DIR, SCREENSHOT_DIR, puppeteer-core

### Community 184 - "2xx — Successful Responses"
Cohesion: 0.40
Nodes (5): 2xx — Successful Responses, HTTP 200 OK, HTTP 201 Created, HTTP 202 Accepted, HTTP 204 No Content

### Community 186 - "vite.config.ts"
Cohesion: 0.22
Nodes (6): @tailwindcss/vite@^4.1.18, vite@^7.2.4, @vitejs/plugin-react@^5.1.1, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 192 - "WatchlistItem"
Cohesion: 0.17
Nodes (4): WatchlistItem, Meta, WatchlistDetailView, WatchlistView

### Community 197 - "5. Deep Dive: HTTP 304 Not Modified & Caching"
Cohesion: 0.40
Nodes (5): 5. Deep Dive: HTTP 304 Not Modified & Caching, Conditional Requests (ETag & Last-Modified), How Browser Caching Works, How Caching Is Implemented in Flick, When 304 Is Healthy vs When It Is a Problem

### Community 198 - "GuestProvisioningAPITests"
Cohesion: 0.05
Nodes (4): ExistingRegisteredUserCompatibilityTests, GuestProvisioningAPITests, GuestRecoveryAPITests, GuestThrottlingTests

### Community 201 - "Swipe"
Cohesion: 0.10
Nodes (7): Swipe, Meta, HistoricalReconciliationService, map_swipe_reaction(), reconcile_historical_interactions(), HistoricalReconciliationServiceTests, Task 3: Historical Interaction Reconciliation Service & Command

### Community 204 - "4. Deciphering Server Logs & Trailing Numbers"
Cohesion: 0.29
Nodes (7): 4. Deciphering Server Logs & Trailing Numbers, Anatomy of a Django/Daphne Access Log, What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery), Why does `/api/curators-selection/` show `200 1989`?, Why does `/api/users/profile/` show `200 55`?, Why does `GET /api/movies/` show `304 -` or `304 0`?, WSGI vs ASGI Logging Differences

### Community 208 - "IntelligenceModelsTestCase"
Cohesion: 0.11
Nodes (5): ProposalOutboxMessage, Meta, ProposalOutboxMessageSerializer, Meta, IntelligenceModelsTestCase

### Community 211 - "InMemoryTokenBucket"
Cohesion: 0.15
Nodes (5): InMemoryTokenBucket, 1. The Movie Database (TMDB), 2. Redis, 3. PostgreSQL & SQLite, External Service Failure Modes (TMDB, Redis, Postgres)

### Community 219 - "SecretRedactionFilter"
Cohesion: 0.10
Nodes (4): CorrelationIdFilter, SecretRedactionFilter, SecretRedactionFormatter, SecretRedactionLoggerTests

### Community 234 - ".compile_manifest"
Cohesion: 0.07
Nodes (5): ScoredCandidate, DeckStateConcurrencyTests, BoutiqueManifestCompilationTests, NormalManifestCompilationTests, ShortageRedistributionAndFloorTests

### Community 244 - "run_staleness_sweep"
Cohesion: 0.06
Nodes (6): Command, StalenessSweepCheckpoint, Meta, run_staleness_sweep(), StalenessSweepService, StalenessSweepTests

### Community 262 - "requests"
Cohesion: 0.12
Nodes (3): Command, Command, fetch_tmdb_movies()

## Knowledge Gaps
- **93 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Movie` connect `Movie` to `PersonalizedRecommendationEngine`, `Phase6BatchBBackendTests`, `SwipeAndMatchingTests`, `django_db`, `_make_movie`, `GuestConversionValidationAndRejectionTests`, `PaginationAndResourceLimitTests`, `handle_catalogue_classification`, `batch3_handlers.py`, `InteractionLogProcessingStatusTests`, `MovieSerializer`, `Batch5PersonalizationEvaluationTests`, `DeckStateAPITests`, `.handle`, `Match`, `DynamicMovieCatalogueTests`, `Command`, `_build_candidate_queryset`, `Stage3EndToEndProductValidationTests`, `ProposalExecutionWorker`, `Pre1990ReleasePeriodFilterTests`, `SessionLifecycleAndQuestionnaireRecoveryTests`, `DiscoverTests`, `transition_movie_classification`, `CatalogueJob`, `MatchListFilteringSecurityTests`, `WorkflowEndToEndIntegrationTests`, `RecommendationDiscoveryTests`, `evaluate_eligibility_predicates`, `test_recommendation_evaluation.py`, `.record_swipe_response`, `admin.py`, `ScreeningSessionResultsAndStatsPersistenceTests`, `views.py`, `_ingest_tmdb_results`, `CorrectSyntheticM1RecordsTest`, `TestCase`, `tmdb.py`, `.enqueue`, `DeckStateError`, `WatchlistItem`, `retrieval.py`, `StreamingProvider`, `update_movie_metadata`, `Swipe`, `Swipe`, `TestIndianLanguageDiscovery`, `batch_sync_prelaunch.py`, `ArchiveShelvesService`, `IntelligenceModelsTestCase`, `TmdbChangesService`, `.anonymize_and_delete_user`, `LocalizedGenreRetrievalTests`, `PostgreSQLQueueConcurrencyTests`, `HardConstraintFilter`, `TestReliabilityAndRetrieval`, `AuthenticationAndPermissionTests`, `StreamingFilterAuditTests`, `.compile_manifest`, `SuperLikePersistenceAndAttributionTests`, `SessionDetailSerializer`, `Phase1EndToEndScenarioTestCase`, `SuperLikeReactionMatrixIntegrationTests`, `DatabaseConcurrencyAndSwipeReliabilityTests`, `run_staleness_sweep`, `UserPreferenceData`, `MotionAndSessionRegressionAuditTests`, `SwipeUndoTests`, `SessionHistoryTests`, `CandidateRetrievalAndEligibilityTests`, `CoreUserExperienceRepairTests`, `_validate_candidate`?**
  _High betweenness centrality (0.258) - this node is a cross-community bridge._
- **Are the 130 inferred relationships involving `Movie` (e.g. with `Command` and `Command`) actually correct?**
  _`Movie` has 130 INFERRED edges - model-reasoned connections that need verification._
- **Should `PersonalizedRecommendationEngine` be split into smaller, more focused modules?**
  _Cohesion score 0.12666666666666668 - nodes in this community are weakly interconnected._
- **Why does `6. Flick-Specific Error Handling Architecture` connect `6. Flick-Specific Error Handling Architecture` to `apiRequest`, `Flick — HTTP Status Codes, Server Logs & Error-Handling Reference`, `InMemoryTokenBucket`?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `Session` (e.g. with `MatchConsumer` and `SessionDetailSerializer`) actually correct?**
  _`Session` has 79 INFERRED edges - model-reasoned connections that need verification._
- **Should `Defense-in-Depth Debugging Strategies` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Why does `Frontend Error Handling (`api.ts` & React)` connect `apiRequest` to `6. Flick-Specific Error Handling Architecture`?**
  _High betweenness centrality (0.154) - this node is a cross-community bridge._